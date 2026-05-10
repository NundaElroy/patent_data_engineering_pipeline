import sys
import sqlite3
import pandas as pd
import json
import os

sys.stdout.reconfigure(encoding="utf-8")

# Configuration
DB_PATH    = "patents.db"
OUTPUT_DIR = "./reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

CPC_LABELS = {
    "A": "Human Necessities",
    "B": "Operations & Transport",
    "C": "Chemistry & Metallurgy",
    "D": "Textiles & Paper",
    "E": "Fixed Constructions",
    "F": "Mechanical Engineering",
    "G": "Physics",
    "H": "Electricity",
    "Y": "New Technologies",
}

def get_conn():
    return sqlite3.connect(DB_PATH)

def run_query(conn, sql):
    return pd.read_sql_query(sql, conn)

def run_cpc_analysis():
    print("Connecting to database...")
    conn = get_conn()

    #
    # CPC Q1 — Patents per Technology Section
    #
    print("Running CPC Q1: Patents by Technology Section...")
    df_cpc_sections = run_query(conn, """
        SELECT cpc_section,
               COUNT(DISTINCT patent_id) AS patents
        FROM cpc
        WHERE cpc_section IS NOT NULL
        GROUP BY cpc_section
        ORDER BY patents DESC;
    """)

    #
    # CPC Q2 — Technology Section Growth by Decade
    #
    print("Running CPC Q2: Technology Growth by Decade...")
    df_cpc_decades = run_query(conn, """
        SELECT c.cpc_section,
               (p.year / 10) * 10          AS decade,
               COUNT(DISTINCT c.patent_id) AS patents
        FROM cpc c
        JOIN patents p ON c.patent_id = p.patent_id
        WHERE p.year IS NOT NULL
          AND p.year >= 1900
          AND c.cpc_section IS NOT NULL
        GROUP BY c.cpc_section, decade
        ORDER BY decade ASC, patents DESC;
    """)

    #
    # CPC Q3 — Top Company per Technology Section
    #
    print("Running CPC Q3: Top Company per Technology Section (this may take a few minutes)...")
    df_cpc_companies = run_query(conn, """
        WITH SectionCompany AS (
            SELECT c.cpc_section,
                   co.name                      AS company_name,
                   COUNT(DISTINCT c.patent_id)  AS patents,
                   RANK() OVER (
                       PARTITION BY c.cpc_section
                       ORDER BY COUNT(DISTINCT c.patent_id) DESC
                   ) AS rnk
            FROM cpc c
            JOIN relationships r ON c.patent_id = r.patent_id
            JOIN companies co    ON r.company_id = co.company_id
            WHERE c.cpc_section IS NOT NULL
              AND co.name IS NOT NULL
              AND co.name != 'Unknown Company'
            GROUP BY c.cpc_section, co.name
        )
        SELECT cpc_section, company_name, patents
        FROM SectionCompany
        WHERE rnk = 1
        ORDER BY patents DESC;
    """)

    conn.close()

    #
    # CSV Exports
    #
    print("\nExporting CSVs...")
    df_cpc_sections.to_csv( f"{OUTPUT_DIR}/cpc_sections.csv",        index=False)
    df_cpc_decades.to_csv(  f"{OUTPUT_DIR}/cpc_growth_by_decade.csv", index=False)
    df_cpc_companies.to_csv(f"{OUTPUT_DIR}/cpc_top_companies.csv",    index=False)

    #
    # JSON Export
    #
    print("Writing CPC JSON report...")
    cpc_report = {
        "cpc_sections"         : df_cpc_sections.to_dict(orient="records"),
        "cpc_growth_by_decade" : df_cpc_decades.to_dict(orient="records"),
        "cpc_top_companies"    : df_cpc_companies.to_dict(orient="records"),
    }
    with open(f"{OUTPUT_DIR}/cpc_report.json", "w", encoding="utf-8") as f:
        json.dump(cpc_report, f, indent=4, ensure_ascii=False)

    #
    # Console Report
    #
    print("\n============== CPC TECHNOLOGY REPORT ================")

    print("\n  Patents by Technology Section:")
    for _, r in df_cpc_sections.iterrows():
        label = CPC_LABELS.get(r["cpc_section"], r["cpc_section"])
        print(f"    {r['cpc_section']} — {label:<25} {int(r['patents']):>10,}")

    print("\n  Technology Growth by Decade (top 3 sections per decade):")
    for decade, group in df_cpc_decades.groupby("decade"):
        print(f"\n    {int(decade)}s:")
        for _, r in group.head(3).iterrows():
            label = CPC_LABELS.get(r["cpc_section"], r["cpc_section"])
            print(f"      {r['cpc_section']} — {label:<25} {int(r['patents']):,}")

    print("\n  Top Company per Technology Section:")
    for _, r in df_cpc_companies.iterrows():
        label = CPC_LABELS.get(r["cpc_section"], r["cpc_section"])
        print(f"    {r['cpc_section']} — {label:<25} {r['company_name']} ({int(r['patents']):,})")

    print("\n=====================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("=====================================================\n")

if __name__ == "__main__":
    run_cpc_analysis()