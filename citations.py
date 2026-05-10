import os
import sqlite3
import zipfile
import requests
import pandas as pd
from collections import Counter

#  Configuration 
RAW_DIR    = "./raw"
CLEAN_DIR  = "./data"
DB_PATH    = "patents.db"

BASE_URL   = "https://s3.amazonaws.com/data.patentsview.org/download/"
FILENAME   = "g_us_patent_citation.tsv.zip"

CHUNK_SIZE = 100_000

os.makedirs(RAW_DIR,   exist_ok=True)
os.makedirs(CLEAN_DIR, exist_ok=True)

#  Step 1: Download 
def download_file():
    tsv_path = os.path.join(RAW_DIR, "g_us_patent_citation.tsv")
    if os.path.exists(tsv_path):
        print(f"g_us_patent_citation.tsv already exists in {RAW_DIR}, skipping download.")
        return

    url      = BASE_URL + FILENAME
    filepath = os.path.join(RAW_DIR, FILENAME)

    print(f"Connecting to {url}...")
    print("Warning: this file is large (5-10GB). This will take a while...")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total      = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        done = int(50 * downloaded / total)
                        bar  = "=" * done + " " * (50 - done)
                        mb   = downloaded / (1024 * 1024)
                        print(f"\r[{bar}] {mb:.0f} MB", end="", flush=True)

    print(f"\nDownload complete: {FILENAME}")

    print(f"Extracting {FILENAME}...")
    with zipfile.ZipFile(filepath, "r") as z:
        z.extractall(RAW_DIR)
    os.remove(filepath)
    print("Extracted and deleted zip.")

#  Step 2: Aggregate citations 
def aggregate_citations():
    filepath = os.path.join(RAW_DIR, "g_us_patent_citation.tsv")
    out_path = os.path.join(CLEAN_DIR, "clean_citations.csv")

    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found. Run download first.")
        return False

    print("\nAggregating citation counts...")
    print("Counting how many times each patent is cited by others...")

    # We only need citation_patent_id (the patent being cited)
    # Count occurrences = how many times that patent was cited
    citation_counts = Counter()

    chunk_num = 0
    for chunk in pd.read_csv(
        filepath,
        sep          = "\t",
        usecols      = ["citation_patent_id"],
        dtype        = str,
        chunksize    = CHUNK_SIZE,
        on_bad_lines = "skip",
    ):
        chunk = chunk.dropna(subset=["citation_patent_id"])
        citation_counts.update(chunk["citation_patent_id"].tolist())
        chunk_num += 1
        print(".", end="", flush=True)

    print(f" Done! Processed {chunk_num * CHUNK_SIZE:,} rows.")

    # Convert counter to dataframe
    print("\nBuilding aggregated dataframe...")
    df = pd.DataFrame(
        citation_counts.items(),
        columns=["patent_id", "citation_count"]
    )
    df["citation_count"] = df["citation_count"].astype(int)
    df = df.sort_values("citation_count", ascending=False)

    df.to_csv(out_path, index=False)
    print(f"Saved clean_citations.csv ({len(df):,} unique cited patents)")
    print(f"Most cited patent: {df.iloc[0]['patent_id']} with {df.iloc[0]['citation_count']:,} citations")
    return True

#  Step 3: Ensure table exists 
def ensure_citations_table(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patent_citations (
            patent_id       VARCHAR(20),
            citation_count  INTEGER,
            FOREIGN KEY (patent_id) REFERENCES patents(patent_id)
        );
        CREATE INDEX IF NOT EXISTS idx_citations_patent ON patent_citations(patent_id);
        CREATE INDEX IF NOT EXISTS idx_citations_count  ON patent_citations(citation_count);
    """)
    print("patent_citations table ready.")

#  Step 4: Load 
def load_citations():
    csv_path = os.path.join(CLEAN_DIR, "clean_citations.csv")
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found. Run aggregation first.")
        return

    print(f"\nLoading clean_citations.csv into database...")

    with sqlite3.connect(DB_PATH) as conn:
        ensure_citations_table(conn)

        # Clear previous load
        conn.execute("DELETE FROM patent_citations")
        conn.commit()

        for chunk in pd.read_csv(csv_path, chunksize=CHUNK_SIZE):
            chunk.to_sql("patent_citations", conn, if_exists="append", index=False)
            print(".", end="", flush=True)

    print(" Finished loading patent_citations.")

#  Step 5: Quick sanity check 
def sanity_check():
    print("\nRunning sanity check...")
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("""
            SELECT 
                COUNT(*)                    AS total_cited_patents,
                SUM(citation_count)         AS total_citations,
                AVG(citation_count)         AS avg_citations,
                MAX(citation_count)         AS max_citations
            FROM patent_citations;
        """, conn)
        print(df.to_string(index=False))

        print("\nTop 10 most cited patents:")
        df_top = pd.read_sql_query("""
            SELECT pc.patent_id, pc.citation_count, p.title
            FROM patent_citations pc
            LEFT JOIN patents p ON pc.patent_id = p.patent_id
            ORDER BY citation_count DESC
            LIMIT 10;
        """, conn)
        print(df_top.to_string(index=False))

def run_load_citations() -> None:
    print("=" * 55)
    print(" Patent Citations Pipeline")
    print("=" * 55)

    download_file()
    success = aggregate_citations()
    if success:
        load_citations()
        sanity_check()
        print("\nCitation pipeline complete. Ready for weighted analysis.")
    else:
        print("\nPipeline aborted. Fix the error above and retry.")


#  Execution
if __name__ == "__main__":
    run_load_citations()