# reports.py
# Generates console report, CSVs, and JSON from SQLite database

import sqlite3
import pandas as pd
import json
import os
import math
from typing import Any

# Configuration 
DB_PATH    = "patents.db"
OUTPUT_DIR = "./reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_conn():
    return sqlite3.connect(DB_PATH)

def run_query(conn, sql):
    return pd.read_sql_query(sql, conn)


def _to_json_safe(value: Any) -> Any:
    """Convert values to something `json.dump(..., allow_nan=False)` can serialize."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None

    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]

    return value

def run_analysis():
    print("Connecting to database. This may take a moment on 9M records...")
    conn = get_conn()

    total = run_query(conn, "SELECT COUNT(*) as count FROM patents").iloc[0]['count']

    # Q1  Top Inventors
    print("Running Q1: Top Inventors...")
    q1 = """
        SELECT i.name,
               COUNT(r.patent_id) AS patents
        FROM inventors i
        JOIN relationships r ON i.inventor_id = r.inventor_id
        WHERE i.name IS NOT NULL
          AND i.name != 'Unknown Inventor'
        GROUP BY i.inventor_id, i.name
        ORDER BY patents DESC
        LIMIT 10;
    """
    df_inventors = run_query(conn, q1)

    # Q2  Top Companies
    print("Running Q2: Top Companies...")
    q2 = """
        SELECT c.name,
               COUNT(r.patent_id) AS patents
        FROM companies c
        JOIN relationships r ON c.company_id = r.company_id
        WHERE c.name IS NOT NULL
          AND c.name != 'Unknown Company'
        GROUP BY c.company_id, c.name
        ORDER BY patents DESC
        LIMIT 10;
    """
    df_companies = run_query(conn, q2)

    # Q3  Countries with share of global patents
    print("Running Q3: Countries...")
    q3 = """
        SELECT i.country,
               COUNT(DISTINCT r.patent_id)                                AS patents,
               ROUND(COUNT(DISTINCT r.patent_id) * 1.0 /
                    (SELECT COUNT(*) FROM patents), 4)                    AS share
        FROM inventors i
        JOIN relationships r ON i.inventor_id = r.inventor_id
        WHERE i.country IS NOT NULL
          AND i.country != 'Unknown'
        GROUP BY i.country
        ORDER BY patents DESC
        LIMIT 10;
    """
    df_countries = run_query(conn, q3)

    # Q4  Trends Over Time
    print("Running Q4: Trends Over Time...")
    q4 = """
        SELECT year,
               COUNT(patent_id) AS patents
        FROM patents
        WHERE year IS NOT NULL
        GROUP BY year
        ORDER BY year ASC;
    """
    df_years = run_query(conn, q4)

    # Q5  JOIN Query (patents + inventors + companies in one result)
    print("Running Q5: JOIN Query...")
    q5 = """
        SELECT p.patent_id,
               p.title,
               p.year,
               i.name    AS inventor_name,
               i.country AS inventor_country,
               c.name    AS company_name
        FROM patents p
        JOIN relationships r ON p.patent_id   = r.patent_id
        JOIN inventors i     ON r.inventor_id  = i.inventor_id
        JOIN companies c     ON r.company_id   = c.company_id
        WHERE p.year      IS NOT NULL
          AND i.name      IS NOT NULL
          AND c.name      IS NOT NULL
        LIMIT 1000;
    """
    df_join = run_query(conn, q5)

    # Q6  CTE Query (3 steps)
    #   Step 1: count patents per inventor
    #   Step 2: count patents per company
    #   Step 3: find top inventor-company pairs and combine both counts
    print("Running Q6: CTE Query...")
    q6 = """
        WITH InventorStats AS (
            SELECT r.inventor_id,
                   i.name                 AS inventor_name,
                   COUNT(r.patent_id)     AS inventor_patents
            FROM relationships r
            JOIN inventors i ON r.inventor_id = i.inventor_id
            WHERE i.name IS NOT NULL
              AND i.name != 'Unknown Inventor'
            GROUP BY r.inventor_id, i.name
        ),
        CompanyStats AS (
            SELECT r.company_id,
                   c.name                 AS company_name,
                   COUNT(r.patent_id)     AS company_patents
            FROM relationships r
            JOIN companies c ON r.company_id = c.company_id
            WHERE c.name IS NOT NULL
              AND c.name != 'Unknown Company'
            GROUP BY r.company_id, c.name
        ),
        PairsRanked AS (
            SELECT ist.inventor_name,
                   cst.company_name,
                   ist.inventor_patents,
                   cst.company_patents,
                   COUNT(r.patent_id)     AS shared_patents
            FROM relationships r
            JOIN InventorStats ist ON r.inventor_id = ist.inventor_id
            JOIN CompanyStats  cst ON r.company_id  = cst.company_id
            GROUP BY ist.inventor_name, cst.company_name,
                     ist.inventor_patents, cst.company_patents
        )
        SELECT inventor_name,
               company_name,
               shared_patents,
               inventor_patents,
               company_patents
        FROM PairsRanked
        ORDER BY shared_patents DESC
        LIMIT 10;
    """
    df_cte = run_query(conn, q6)

    # Q7  Ranking Query (DENSE_RANK inventors within each country)
    print("Running Q7: Ranking Query...")
    q7 = """
        SELECT country,
               inventor_name,
               patents,
               DENSE_RANK() OVER (
                   PARTITION BY country
                   ORDER BY patents DESC
               ) AS country_rank
        FROM (
            SELECT i.country,
                   i.name             AS inventor_name,
                   COUNT(r.patent_id) AS patents
            FROM inventors i
            JOIN relationships r ON i.inventor_id = r.inventor_id
            WHERE i.country IS NOT NULL
              AND i.name    IS NOT NULL
              AND i.name != 'Unknown Inventor'
            GROUP BY i.country, i.inventor_id, i.name
        ) base
        ORDER BY country ASC, country_rank ASC;
    """
    df_ranked = run_query(conn, q7)
    # keep only top 3 per country for reports
    df_ranked = df_ranked[df_ranked['country_rank'] <= 3]

    # EXTRA 1  Year-over-Year Growth Rate  (LAG via pandas, SQLite safe)
    print("Running Extra: Growth Rate...")
    df_growth = df_years.copy()
    df_growth['prev_year_patents'] = df_growth['patents'].shift(1)
    df_growth['growth_pct'] = (
        (df_growth['patents'] - df_growth['prev_year_patents'])
        / df_growth['prev_year_patents'] * 100
    ).round(2)

    # EXTRA 2  Rolling 5-Year Average
    print("Running Extra: Rolling Average...")
    df_growth['rolling_5yr_avg'] = (
        df_growth['patents']
        .rolling(window=5, min_periods=1)
        .mean()
        .round(0)
    )

    # EXTRA 3  Peak Year
    peak_row  = df_years.loc[df_years['patents'].idxmax()]
    peak_year = int(peak_row['year'])
    peak_cnt  = int(peak_row['patents'])

    # EXTRA 4  Solo vs Team Patents
    print("Running Extra: Solo vs Team...")
    q_team = """
        WITH InventorCount AS (
            SELECT patent_id,
                   COUNT(DISTINCT inventor_id) AS num_inventors
            FROM relationships
            GROUP BY patent_id
        )
        SELECT CASE
                   WHEN num_inventors = 1 THEN 'Solo'
                   WHEN num_inventors BETWEEN 2 AND 4 THEN 'Small Team (2-4)'
                   ELSE 'Large Team (5+)'
               END                          AS inventor_type,
               COUNT(*)                     AS patents,
               ROUND(COUNT(*) * 100.0 /
                    (SELECT COUNT(*) FROM patents), 2) AS share_pct
        FROM InventorCount
        GROUP BY inventor_type
        ORDER BY patents DESC;
    """
    df_team = run_query(conn, q_team)

    # EXTRA 5  Top Company Per Decade
    print("Running Extra: Top Company per Decade...")
    q_decade = """
        WITH DecadePatents AS (
            SELECT c.name                          AS company_name,
                   (p.year / 10) * 10              AS decade,
                   COUNT(r.patent_id)              AS patents
            FROM patents p
            JOIN relationships r ON p.patent_id  = r.patent_id
            JOIN companies c     ON r.company_id  = c.company_id
            WHERE p.year IS NOT NULL
              AND c.name IS NOT NULL
              AND c.name != 'Unknown Company'
            GROUP BY c.name, decade
        ),
        RankedDecade AS (
            SELECT company_name,
                   decade,
                   patents,
                   RANK() OVER (
                       PARTITION BY decade
                       ORDER BY patents DESC
                   ) AS rnk
            FROM DecadePatents
        )
        SELECT decade,
               company_name,
               patents
        FROM RankedDecade
        WHERE rnk = 1
        ORDER BY decade ASC;
    """
    df_decade = run_query(conn, q_decade)

    # EXTRA 6  Top Inventor per Country
    print("Running Extra: Top Inventor per Country...")
    q_top_per_country = """
        WITH InvCountry AS (
            SELECT i.country,
                   i.name                     AS inventor_name,
                   COUNT(r.patent_id)          AS patents,
                   DENSE_RANK() OVER (
                       PARTITION BY i.country
                       ORDER BY COUNT(r.patent_id) DESC
                   )                           AS rnk
            FROM inventors i
            JOIN relationships r ON i.inventor_id = r.inventor_id
            WHERE i.country IS NOT NULL
              AND i.name    IS NOT NULL
              AND i.name != 'Unknown Inventor'
            GROUP BY i.country, i.inventor_id, i.name
        )
        SELECT country, inventor_name, patents
        FROM InvCountry
        WHERE rnk = 1
        ORDER BY patents DESC
        LIMIT 20;
    """
    df_top_per_country = run_query(conn, q_top_per_country)

    # CPC Q1  Patents per Technology Section
    print("Running CPC Q1: Patents by Technology Section...")
    df_cpc_sections = run_query(conn, """
        SELECT cpc_section,
               COUNT(DISTINCT patent_id) AS patents
        FROM cpc
        WHERE cpc_section IS NOT NULL
        GROUP BY cpc_section
        ORDER BY patents DESC;
    """)

    # CPC Q2  Technology Section Growth by Decade
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

    # CPC Q3  Top Company per Technology Section
    print("Running CPC Q3: Top Company per Technology Section...")
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

    # CSV EXPORTS
    print("\nExporting CSVs...")
    df_inventors.to_csv(       f"{OUTPUT_DIR}/top_inventors.csv",            index=False)
    df_companies.to_csv(       f"{OUTPUT_DIR}/top_companies.csv",            index=False)
    df_countries.to_csv(       f"{OUTPUT_DIR}/top_countries.csv",            index=False)
    df_years.to_csv(           f"{OUTPUT_DIR}/country_trends.csv",           index=False)
    df_growth.to_csv(          f"{OUTPUT_DIR}/growth_rate.csv",              index=False)
    df_team.to_csv(            f"{OUTPUT_DIR}/solo_vs_team.csv",             index=False)
    df_decade.to_csv(          f"{OUTPUT_DIR}/top_company_per_decade.csv",   index=False)
    df_ranked.to_csv(          f"{OUTPUT_DIR}/inventors_by_country.csv",     index=False)
    df_top_per_country.to_csv( f"{OUTPUT_DIR}/top_inventor_per_country.csv", index=False)
    df_join.to_csv(            f"{OUTPUT_DIR}/patents_full_join.csv",        index=False)
    df_cte.to_csv(             f"{OUTPUT_DIR}/inventor_company_pairs.csv",   index=False)
    df_cpc_sections.to_csv(    f"{OUTPUT_DIR}/cpc_sections.csv",             index=False)
    df_cpc_decades.to_csv(     f"{OUTPUT_DIR}/cpc_growth_by_decade.csv",     index=False)
    df_cpc_companies.to_csv(   f"{OUTPUT_DIR}/cpc_top_companies.csv",        index=False)

    # JSON REPORT
    print("Writing JSON report...")
    report = {
        "total_patents"            : int(total),
        "peak_year"                : {"year": peak_year, "patents": peak_cnt},
        "top_inventors"            : df_inventors.to_dict(orient="records"),
        "top_companies"            : df_companies.to_dict(orient="records"),
        "top_countries"            : df_countries.to_dict(orient="records"),
        "yearly_trends"            : df_growth.to_dict(orient="records"),
        "solo_vs_team"             : df_team.to_dict(orient="records"),
        "top_company_per_decade"   : df_decade.to_dict(orient="records"),
        "top_inventor_per_country" : df_top_per_country.to_dict(orient="records"),
        "inventor_company_pairs"   : df_cte.to_dict(orient="records"),
        "inventors_by_country"     : df_ranked.to_dict(orient="records"),
        "cpc_sections"             : df_cpc_sections.to_dict(orient="records"),
        "cpc_growth_by_decade"     : df_cpc_decades.to_dict(orient="records"),
        "cpc_top_companies"        : df_cpc_companies.to_dict(orient="records"),
    }

    with open(f"{OUTPUT_DIR}/report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    # CONSOLE REPORT
    print("\n==================== PATENT REPORT ====================")
    print(f"  Total Patents : {int(total):,}")
    print(f"  Peak Year     : {peak_year} ({peak_cnt:,} patents)\n")

    print("  Top Inventors:")
    for i, r in df_inventors.iterrows():
        print(f"    {i+1}. {r['name']}  {int(r['patents']):,}")

    print("\n  Top Companies:")
    for i, r in df_companies.iterrows():
        print(f"    {i+1}. {r['name']}  {int(r['patents']):,}")

    print("\n  Top Countries:")
    for i, r in df_countries.iterrows():
        print(f"    {i+1}. {r['country']}  {int(r['patents']):,} ({float(r['share'])*100:.1f}%)")

    print("\n  Patent Growth (last 5 years on record):")
    for _, r in df_growth.tail(5).iterrows():
        pct = r['growth_pct']
        if pd.notna(pct):
            arrow = "▲" if pct > 0 else "▼"
            print(f"    {int(r['year'])}: {int(r['patents']):,}  {arrow} {abs(pct)}%")
        else:
            print(f"    {int(r['year'])}: {int(r['patents']):,}")

    print("\n  Solo vs Team Patents:")
    for _, r in df_team.iterrows():
        print(f"    {r['inventor_type']}: {int(r['patents']):,} ({r['share_pct']}%)")

    print("\n  Top Company Per Decade:")
    for _, r in df_decade.iterrows():
        print(f"    {int(r['decade'])}s: {r['company_name']}  {int(r['patents']):,}")
    
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

    print("\n  Patents by Technology Section:")
    for _, r in df_cpc_sections.iterrows():
        label = CPC_LABELS.get(r["cpc_section"], r["cpc_section"])
        print(f"    {r['cpc_section']}  {label:<25} {int(r['patents']):>10,}")

    print("\n  Top Company per Technology Section:")
    for _, r in df_cpc_companies.iterrows():
        label = CPC_LABELS.get(r["cpc_section"], r["cpc_section"])
        print(f"    {r['cpc_section']}  {label:<25} {r['company_name']} ({int(r['patents']):,})")

    print("=======================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("=======================================================\n")

if __name__ == "__main__":
    run_analysis()