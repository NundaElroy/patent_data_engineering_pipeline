import os
import sqlite3
import zipfile
import requests
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────
RAW_DIR   = "./raw"
CLEAN_DIR = "./data"
DB_PATH   = "patents.db"

BASE_URL  = "https://s3.amazonaws.com/data.patentsview.org/download/"
FILENAME  = "g_cpc_current.tsv.zip"

os.makedirs(RAW_DIR,   exist_ok=True)
os.makedirs(CLEAN_DIR, exist_ok=True)

CHUNK_SIZE = 100_000

# ── Step 1: Download ──────────────────────────────────────────────────────
def download_file():
    url      = BASE_URL + FILENAME
    filepath = os.path.join(RAW_DIR, FILENAME)

    if os.path.exists(filepath.replace(".zip", "")):
        print(f"g_cpc_current.tsv already exists in {RAW_DIR}, skipping download.")
        return

    print(f"Connecting to {url}...")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total         = int(r.headers.get("content-length", 0))
        downloaded    = 0

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        done = int(50 * downloaded / total)
                        bar  = "=" * done + " " * (50 - done)
                        mb   = downloaded / (1024 * 1024)
                        print(f"\r[{bar}] {mb:.2f} MB", end="", flush=True)

    print(f"\nDownload complete: {FILENAME}")

    print(f"Extracting {FILENAME}...")
    with zipfile.ZipFile(filepath, "r") as z:
        z.extractall(RAW_DIR)
    os.remove(filepath)
    print("Extracted and deleted zip.")

# ── Step 2: Clean ─────────────────────────────────────────────────────────
def clean_cpc():
    filepath = os.path.join(RAW_DIR, "g_cpc_current.tsv")
    out_path = os.path.join(CLEAN_DIR, "clean_cpc.csv")

    print("\nCleaning CPC data...")

    chunks = []
    for chunk in pd.read_csv(
        filepath,
        sep       = "\t",
        usecols   = ["patent_id", "cpc_section", "cpc_type"],
        dtype     = str,
        chunksize = CHUNK_SIZE,
        on_bad_lines = "skip",
    ):
        # Keep only inventional classifications to avoid double-counting
        chunk = chunk[chunk["cpc_type"] == "inventional"]
        chunk = chunk.dropna(subset=["patent_id", "cpc_section"])
        # One section per patent (take first inventional classification only)
        chunks.append(chunk)
        print(".", end="", flush=True)

    print(" Done!")
    df = pd.concat(chunks, ignore_index=True)

    # Drop duplicate patent_id + cpc_section pairs
    df = df.drop_duplicates(subset=["patent_id", "cpc_section"])

    df.to_csv(out_path, index=False)
    print(f"Saved clean_cpc.csv ({len(df):,} rows)")
    return df

# ── Step 3: Create CPC table if missing ──────────────────────────────────
def ensure_cpc_table(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cpc (
            patent_id   VARCHAR(20),
            cpc_section VARCHAR(10),
            cpc_type    VARCHAR(36),
            FOREIGN KEY (patent_id) REFERENCES patents(patent_id)
        );
        CREATE INDEX IF NOT EXISTS idx_cpc_patent  ON cpc(patent_id);
        CREATE INDEX IF NOT EXISTS idx_cpc_section ON cpc(cpc_section);
    """)
    print("CPC table ready.")

# ── Step 4: Load ──────────────────────────────────────────────────────────
def load_cpc():
    csv_path = os.path.join(CLEAN_DIR, "clean_cpc.csv")
    print(f"\nLoading clean_cpc.csv into database...")

    with sqlite3.connect(DB_PATH) as conn:
        ensure_cpc_table(conn)

        # Clear any previous load so we don't duplicate
        conn.execute("DELETE FROM cpc")
        conn.commit()

        for chunk in pd.read_csv(csv_path, chunksize=CHUNK_SIZE):
            chunk.to_sql("cpc", conn, if_exists="append", index=False)
            print(".", end="", flush=True)

    print(f" Finished loading CPC table.")

# ── Execution ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print(" CPC Data Pipeline")
    print("=" * 50)

    download_file()
    clean_cpc()
    load_cpc()

    print("\nCPC pipeline complete. Ready for analysis.")