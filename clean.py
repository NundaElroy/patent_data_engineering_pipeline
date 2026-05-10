import pandas as pd
import os

#  Configuration 
RAW_DIR = "./raw"
CLEAN_DIR = "./data"
os.makedirs(CLEAN_DIR, exist_ok=True)

CHUNK_SIZE = 100000  # Process 100k rows at a time to strictly control RAM

def process_in_chunks(filename, usecols, drop_subset=None):
    """Reads a file in chunks, keeps only required columns, and drops null primary keys."""
    filepath = os.path.join(RAW_DIR, filename)
    print(f"Extracting {filename}...")
    
    chunks = []
    for chunk in pd.read_csv(filepath, sep="\t", usecols=usecols, dtype=str, chunksize=CHUNK_SIZE, on_bad_lines='skip'):
        if drop_subset:
            # Clean: Remove rows where critical IDs are missing
            chunk = chunk.dropna(subset=drop_subset)
        chunks.append(chunk)
        print(".", end="", flush=True)
        
    print(" Done!")
    return pd.concat(chunks, ignore_index=True)

def run_clean() -> None:
    #  1. Clean Locations (Lookup Table)
    print("\n--- Processing Locations ---")
    # Locations is small enough to read directly without chunking
    df_locations = pd.read_csv(
        os.path.join(RAW_DIR, "g_location_disambiguated.tsv"),
        sep="\t",
        usecols=["location_id", "disambig_country"],
        dtype=str,
    )
    df_locations = df_locations.dropna(subset=["location_id"])
    df_locations = df_locations.rename(columns={"disambig_country": "country"})

    #  2. Clean Companies (Assignees) ─
    print("\n--- Processing Companies ---")
    df_assignees = process_in_chunks(
        "g_assignee_disambiguated.tsv",
        ["patent_id", "assignee_id", "disambig_assignee_organization"],
        ["assignee_id", "patent_id"],
    )

    # Clean: Rename columns to match schema
    df_companies = df_assignees[["assignee_id", "disambig_assignee_organization"]].copy()
    df_companies.rename(
        columns={"assignee_id": "company_id", "disambig_assignee_organization": "name"},
        inplace=True,
    )

    # Clean: Handle missing names and duplicates
    df_companies["name"] = df_companies["name"].fillna("Unknown Company")
    df_companies = df_companies.drop_duplicates(subset=["company_id"])

    df_companies.to_csv(os.path.join(CLEAN_DIR, "clean_companies.csv"), index=False)
    print(f"Saved clean_companies.csv ({len(df_companies)} rows)")

    #  3. Clean Inventors ─
    print("\n--- Processing Inventors ---")
    df_inventors_raw = process_in_chunks(
        "g_inventor_disambiguated.tsv",
        [
            "patent_id",
            "inventor_id",
            "disambig_inventor_name_first",
            "disambig_inventor_name_last",
            "location_id",
        ],
        ["inventor_id", "patent_id"],
    )

    # Clean: Concatenate first and last name into a single "name" column
    df_inventors_raw["name"] = df_inventors_raw["disambig_inventor_name_first"].fillna("") + " " + df_inventors_raw[
        "disambig_inventor_name_last"
    ].fillna("")
    df_inventors_raw["name"] = df_inventors_raw["name"].str.strip()
    df_inventors_raw["name"] = df_inventors_raw["name"].replace("", "Unknown Inventor")

    # Clean: Merge with locations to get the country, fill missing with 'Unknown'
    df_inventors = df_inventors_raw[["inventor_id", "name", "location_id"]].copy()
    df_inventors = pd.merge(df_inventors, df_locations, on="location_id", how="left")
    df_inventors["country"] = df_inventors["country"].fillna("Unknown")

    # Clean: Drop the location_id (not in schema) and remove duplicate inventors
    df_inventors = df_inventors[["inventor_id", "name", "country"]]
    df_inventors = df_inventors.drop_duplicates(subset=["inventor_id"])

    df_inventors.to_csv(os.path.join(CLEAN_DIR, "clean_inventors.csv"), index=False)
    print(f"Saved clean_inventors.csv ({len(df_inventors)} rows)")

    #  4. Build Relationships Table ─
    print("\n--- Processing Relationships ---")
    # We need patent_id, inventor_id, and company_id in one table.
    # We join our extracted assignee and inventor dataframes on patent_id.
    df_rel_inventor = df_inventors_raw[["patent_id", "inventor_id"]]
    df_rel_company = df_assignees[["patent_id", "assignee_id"]].rename(columns={"assignee_id": "company_id"})

    df_relationships = pd.merge(df_rel_inventor, df_rel_company, on="patent_id", how="inner")

    # Clean: Drop duplicate relationship links
    df_relationships = df_relationships.drop_duplicates()

    df_relationships.to_csv(os.path.join(CLEAN_DIR, "clean_relationships.csv"), index=False)
    print(f"Saved clean_relationships.csv ({len(df_relationships)} rows)")

    #  5. Clean Patents ─
    print("\n--- Processing Patents ---")
    df_titles = process_in_chunks("g_patent.tsv", ["patent_id", "patent_title"], ["patent_id"])
    df_abstracts = process_in_chunks("g_patent_abstract.tsv", ["patent_id", "patent_abstract"], ["patent_id"])
    df_dates = process_in_chunks("g_application.tsv", ["patent_id", "filing_date"], ["patent_id"])

    # Clean: Format dates and extract the year
    df_dates["filing_date"] = pd.to_datetime(df_dates["filing_date"], errors="coerce")
    df_dates["year"] = df_dates["filing_date"].dt.year
    # Convert year to nullable integer format, dates to standard string format
    df_dates["year"] = df_dates["year"].astype("Int64")
    df_dates["filing_date"] = df_dates["filing_date"].dt.strftime("%Y-%m-%d")

    # Merge all three patent components together on patent_id
    df_patents = pd.merge(df_titles, df_abstracts, on="patent_id", how="left")
    df_patents = pd.merge(df_patents, df_dates, on="patent_id", how="left")

    # Clean: Rename columns to match the strict schema
    df_patents.rename(columns={"patent_title": "title", "patent_abstract": "abstract"}, inplace=True)

    # Clean: Handle missing values and drop duplicate patent_ids
    df_patents["title"] = df_patents["title"].fillna("No Title")
    df_patents["abstract"] = df_patents["abstract"].fillna("No Abstract")
    df_patents = df_patents.drop_duplicates(subset=["patent_id"])

    df_patents.to_csv(os.path.join(CLEAN_DIR, "clean_patents.csv"), index=False)
    print(f"Saved clean_patents.csv ({len(df_patents)} rows)")

    #  6. Clean CPC ─
    print("\n--- Processing CPC Classifications ---")
    df_cpc = process_in_chunks(
        "g_cpc_current.tsv",
        ["patent_id", "cpc_section", "cpc_type"],
        drop_subset=["patent_id", "cpc_section"],
    )

    # Keep only inventional classifications to avoid double-counting
    df_cpc = df_cpc[df_cpc["cpc_type"] == "inventional"]

    # Drop duplicate patent_id + cpc_section pairs
    df_cpc = df_cpc.drop_duplicates(subset=["patent_id", "cpc_section"])

    df_cpc.to_csv(os.path.join(CLEAN_DIR, "clean_cpc.csv"), index=False)
    print(f"Saved clean_cpc.csv ({len(df_cpc):,} rows)")

    #  7. Clean CPC Detail (Subclass level) ─
    print("\n--- Processing CPC Detail (Subclass) ---")
    df_cpc_detail = process_in_chunks(
        "g_cpc_current.tsv",
        ["patent_id", "cpc_section", "cpc_subclass", "cpc_type"],
        drop_subset=["patent_id", "cpc_section", "cpc_subclass"],
    )
    df_cpc_detail = df_cpc_detail[df_cpc_detail["cpc_type"] == "inventional"]
    df_cpc_detail = df_cpc_detail[["patent_id", "cpc_subclass", "cpc_section"]]
    df_cpc_detail = df_cpc_detail.drop_duplicates(subset=["patent_id", "cpc_subclass"])
    df_cpc_detail.to_csv(os.path.join(CLEAN_DIR, "clean_cpc_detail.csv"), index=False)
    print(f"Saved clean_cpc_detail.csv ({len(df_cpc_detail):,} rows)")

    print("\nData pipeline extraction and cleaning complete! Files are in ./data")


if __name__ == "__main__":
    run_clean()