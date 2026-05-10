import os
import sqlite3
import pandas as pd

# ── Configuration ─────────────────────────────────────────────────────────
RAW_DIR    = "./raw"
CLEAN_DIR  = "./data"
DB_PATH    = "patents.db"
CHUNK_SIZE = 100_000

os.makedirs(CLEAN_DIR, exist_ok=True)

# ── Step 1: Clean ─────────────────────────────────────────────────────────
def clean_cpc_detail():
    filepath = os.path.join(RAW_DIR, "g_cpc_current.tsv")
    out_path = os.path.join(CLEAN_DIR, "clean_cpc_detail.csv")

    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found. Run download.py first.")
        return False

    print("Cleaning CPC detail data (subclass level)...")
    chunks = []
    for chunk in pd.read_csv(
        filepath,
        sep          = "\t",
        usecols      = ["patent_id", "cpc_section", "cpc_subclass", "cpc_type"],
        dtype        = str,
        chunksize    = CHUNK_SIZE,
        on_bad_lines = "skip",
    ):
        # Keep only inventional classifications
        chunk = chunk[chunk["cpc_type"] == "inventional"]
        chunk = chunk.dropna(subset=["patent_id", "cpc_section", "cpc_subclass"])

        # Drop cpc_type — not needed in this table
        chunk = chunk[["patent_id", "cpc_subclass", "cpc_section"]]
        chunks.append(chunk)
        print(".", end="", flush=True)

    print(" Done!")
    df = pd.concat(chunks, ignore_index=True)

    # Drop duplicate patent_id + cpc_subclass pairs
    df = df.drop_duplicates(subset=["patent_id", "cpc_subclass"])

    df.to_csv(out_path, index=False)
    print(f"Saved clean_cpc_detail.csv ({len(df):,} rows)")
    return True

# ── Step 2: Ensure table exists ───────────────────────────────────────────
def ensure_cpc_detail_table(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cpc_detail (
            patent_id    VARCHAR(20),
            cpc_subclass VARCHAR(20),
            cpc_section  VARCHAR(10),
            FOREIGN KEY (patent_id) REFERENCES patents(patent_id)
        );
        CREATE INDEX IF NOT EXISTS idx_cpc_detail_patent   ON cpc_detail(patent_id);
        CREATE INDEX IF NOT EXISTS idx_cpc_detail_subclass ON cpc_detail(cpc_subclass);
        CREATE INDEX IF NOT EXISTS idx_cpc_detail_section  ON cpc_detail(cpc_section);
    """)
    print("cpc_detail table ready.")

# ── Step 3: Load ──────────────────────────────────────────────────────────
def load_cpc_detail():
    csv_path = os.path.join(CLEAN_DIR, "clean_cpc_detail.csv")
    print(f"\nLoading clean_cpc_detail.csv into database...")

    with sqlite3.connect(DB_PATH) as conn:
        ensure_cpc_detail_table(conn)

        # Clear any previous load to avoid duplicates
        conn.execute("DELETE FROM cpc_detail")
        conn.commit()

        for chunk in pd.read_csv(csv_path, chunksize=CHUNK_SIZE, dtype=str):
            chunk.to_sql("cpc_detail", conn, if_exists="append", index=False)
            print(".", end="", flush=True)

    print(" Finished loading cpc_detail.")

# ── Execution ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print(" CPC Detail (Subclass) Pipeline")
    print("=" * 50)

    success = clean_cpc_detail()
    if success:
        load_cpc_detail()
        print("\nCPC detail pipeline complete. Ready for subclass analysis.")
    else:
        print("\nPipeline aborted. Fix the error above and retry.")