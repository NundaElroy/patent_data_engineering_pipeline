import sqlite3
import pandas as pd
import os

from citations import run_load_citations

#  Configuration 
CLEAN_DIR = "./data"
DB_PATH = "patents.db"
SCHEMA_PATH = "schema.sql"
CHUNK_SIZE = 100000  # Insert 100k rows per database transaction

def setup_database():
    """Creates the database and applies the schema.sql file."""
    print("Setting up the database schema...")
    with sqlite3.connect(DB_PATH) as conn:
        with open(SCHEMA_PATH, 'r') as f:
            schema_script = f.read()
        conn.executescript(schema_script)
    print("Schema applied successfully.\n")

def load_csv_to_table(csv_filename, table_name):
    """Reads a clean CSV in chunks and securely inserts it into the SQLite table."""
    csv_path = os.path.join(CLEAN_DIR, csv_filename)
    if not os.path.exists(csv_path):
        print(f"Error: {csv_filename} not found.")
        return

    print(f"Loading {csv_filename} into the '{table_name}' table...")
    
    # Connect to the database
    with sqlite3.connect(DB_PATH) as conn:
        # Read the CSV in chunks to maintain low memory usage
        for chunk in pd.read_csv(csv_path, chunksize=CHUNK_SIZE):
            # to_sql automatically converts the pandas dataframe to SQL INSERT statements
            # if_exists='append' ensures we just add to the tables created by our schema
            # index=False prevents pandas from inserting its own row numbers
            chunk.to_sql(table_name, conn, if_exists='append', index=False)
            print(".", end="", flush=True)
            
    print(f" Finished loading {table_name}.")

def run_load() -> None:
    print("Starting Database Loading Phase...")

    # 1. Initialize the empty database structure
    setup_database()

    # 2. Load the data.
    # Order matters! Load primary tables before the relationship table.
    load_csv_to_table("clean_companies.csv", "companies")
    load_csv_to_table("clean_inventors.csv", "inventors")
    load_csv_to_table("clean_patents.csv", "patents")

    # Load the massive relationship table last
    load_csv_to_table("clean_relationships.csv", "relationships")
    load_csv_to_table("clean_cpc.csv", "cpc")
    load_csv_to_table("clean_cpc_detail.csv", "cpc_detail")

    print("\nDatabase loading complete! You are ready to query patents.db")
    run_load_citations()


#  Execution 
if __name__ == "__main__":
    run_load()