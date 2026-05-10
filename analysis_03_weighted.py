import sys
import sqlite3
import pandas as pd
import json
import os
import math
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

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

def _to_json_safe(value: Any) -> Any:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(v) for v in value]
    return value

def run_weighted_analysis():
    print("Connecting to database...")
    conn = get_conn()

    # W1: Top Inventors by H-Index
    # H-index = largest N where inventor has N patents each cited >= N times
    # Directly proves: prolific != influential
    print("\nRunning W1: Top Inventors by H-Index...")
    q_w1 = """
        WITH InvPatentCitations AS (
            SELECT
                i.inventor_id,
                i.name,
                pc.citation_count,
                ROW_NUMBER() OVER (
                    PARTITION BY i.inventor_id
                    ORDER BY pc.citation_count DESC
                ) AS patent_rank
            FROM inventors i
            JOIN relationships r     ON i.inventor_id = r.inventor_id
            JOIN patent_citations pc ON r.patent_id   = pc.patent_id
            WHERE i.name IS NOT NULL
              AND i.name != 'Unknown Inventor'
        )
        SELECT
            name,
            MAX(patent_rank)              AS h_index,
            COUNT(*)                      AS cited_patents,
            SUM(citation_count)           AS total_citations,
            ROUND(AVG(citation_count), 2) AS avg_citations
        FROM InvPatentCitations
        WHERE patent_rank <= citation_count
        GROUP BY inventor_id, name
        ORDER BY h_index DESC
        LIMIT 10;
    """
    df_w1 = run_query(conn, q_w1)

    q_w1_raw = """
        SELECT i.name,
               COUNT(r.patent_id) AS raw_patents
        FROM inventors i
        JOIN relationships r ON i.inventor_id = r.inventor_id
        WHERE i.name IS NOT NULL
          AND i.name != 'Unknown Inventor'
        GROUP BY i.inventor_id, i.name
        ORDER BY raw_patents DESC
        LIMIT 10;
    """
    df_w1_raw = run_query(conn, q_w1_raw)

    # W2: Top Companies by Total Citation Score
    # SUM of all citations across all company patents
    # Proves: biggest filer != most influential
    print("Running W2: Top Companies by Citation Score...")
    q_w2 = """
        SELECT
            c.name,
            COUNT(DISTINCT r.patent_id)      AS patent_count,
            SUM(pc.citation_count)           AS total_citations,
            ROUND(AVG(pc.citation_count), 2) AS avg_citations_per_patent,
            MAX(pc.citation_count)           AS max_single_patent_citations
        FROM companies c
        JOIN relationships r     ON c.company_id = r.company_id
        JOIN patent_citations pc ON r.patent_id  = pc.patent_id
        WHERE c.name IS NOT NULL
          AND c.name != 'Unknown Company'
        GROUP BY c.company_id, c.name
        ORDER BY total_citations DESC
        LIMIT 10;
    """
    df_w2 = run_query(conn, q_w2)

    # W3: Field-Normalized Company Ranking
    # Divides company citation score by average citations in that CPC section
    # Removes field bias — computing patents cite heavily by nature
    # A pharma patent with 10 citations outperforms computing patent with 10
    # because pharma field average is 3 vs computing field average of 15
    print("Running W3: Field-Normalized Company Rankings (this may take a few minutes)...")
    q_w3 = """
        WITH SectionAvg AS (
            SELECT
                cd.cpc_section,
                AVG(pc.citation_count)       AS avg_section_citations,
                COUNT(DISTINCT cd.patent_id) AS section_total_patents
            FROM cpc_detail cd
            JOIN patent_citations pc ON cd.patent_id = pc.patent_id
            WHERE cd.cpc_section IS NOT NULL
            GROUP BY cd.cpc_section
        ),
        CompanySectionCitations AS (
            SELECT
                co.name                     AS company_name,
                cd.cpc_section,
                COUNT(DISTINCT r.patent_id) AS company_patents_in_section,
                SUM(pc.citation_count)      AS company_citations_in_section
            FROM companies co
            JOIN relationships r     ON co.company_id = r.company_id
            JOIN patent_citations pc ON r.patent_id   = pc.patent_id
            JOIN cpc_detail cd       ON r.patent_id   = cd.patent_id
            WHERE co.name IS NOT NULL
              AND co.name != 'Unknown Company'
              AND cd.cpc_section IS NOT NULL
            GROUP BY co.name, cd.cpc_section
        ),
        Normalized AS (
            SELECT
                csc.company_name,
                csc.cpc_section,
                csc.company_patents_in_section,
                csc.company_citations_in_section,
                sa.avg_section_citations,
                ROUND(
                    csc.company_citations_in_section /
                    NULLIF(sa.avg_section_citations, 0),
                2) AS normalized_score
            FROM CompanySectionCitations csc
            JOIN SectionAvg sa ON csc.cpc_section = sa.cpc_section
        ),
        RankedNormalized AS (
            SELECT *,
                RANK() OVER (
                    PARTITION BY cpc_section
                    ORDER BY normalized_score DESC
                ) AS section_rank
            FROM Normalized
        )
        SELECT
            company_name,
            cpc_section,
            company_patents_in_section,
            company_citations_in_section,
            ROUND(avg_section_citations, 2) AS field_avg_citations,
            normalized_score
        FROM RankedNormalized
        WHERE section_rank = 1
        ORDER BY normalized_score DESC;
    """
    df_w3 = run_query(conn, q_w3)

    conn.close()

    # 
    # CSV Exports 
    
    print("\nExporting CSVs...")
    df_w1.to_csv(     f"{OUTPUT_DIR}/weighted_inventors_hindex.csv",     index=False)
    df_w1_raw.to_csv( f"{OUTPUT_DIR}/weighted_inventors_raw.csv",        index=False)
    df_w2.to_csv(     f"{OUTPUT_DIR}/weighted_companies_citations.csv",  index=False)
    df_w3.to_csv(     f"{OUTPUT_DIR}/weighted_companies_normalized.csv", index=False)

    # 
    # JSON Export 
    
    print("Writing weighted rankings JSON...")
    report = {
        "weighted_inventors_hindex"     : df_w1.to_dict(orient="records"),
        "weighted_inventors_raw"        : df_w1_raw.to_dict(orient="records"),
        "weighted_companies_citations"  : df_w2.to_dict(orient="records"),
        "weighted_companies_normalized" : df_w3.to_dict(orient="records"),
    }
    with open(f"{OUTPUT_DIR}/weighted_report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    # 
    # Console Report 
    #     print("\n========= SECTION 1: CITATION-WEIGHTED RANKINGS =========")

    print("\n  W1: Top Inventors — Raw Count vs H-Index")
    print(f"  {'Rank':<5} {'Raw Count Ranking':<38} {'H-Index Ranking':<38}")
    print(f"  {'-'*5} {'-'*38} {'-'*38}")
    for i in range(min(10, len(df_w1_raw), len(df_w1))):
        raw_row = df_w1_raw.iloc[i]
        idx_row = df_w1.iloc[i]
        raw_str = f"{raw_row['name'][:30]} ({int(raw_row['raw_patents']):,})"
        idx_str = f"{idx_row['name'][:28]} (h={int(idx_row['h_index'])})"
        print(f"  {i+1:<5} {raw_str:<38} {idx_str:<38}")

    print("\n  W2: Top Companies by Total Citation Score")
    print(f"  {'Rank':<5} {'Company':<45} {'Patents':>8} {'Total Cites':>12} {'Avg/Patent':>10}")
    print(f"  {'-'*5} {'-'*45} {'-'*8} {'-'*12} {'-'*10}")
    for i, r in df_w2.iterrows():
        print(f"  {i+1:<5} {str(r['name'])[:43]:<45} "
              f"{int(r['patent_count']):>8,} "
              f"{int(r['total_citations']):>12,} "
              f"{float(r['avg_citations_per_patent']):>10.1f}")

    print("\n  W3: Top Company Per Section (Field-Normalized)")
    print(f"  {'Sec':<5} {'Label':<28} {'Company':<38} {'Norm Score':>10}")
    print(f"  {'-'*5} {'-'*28} {'-'*38} {'-'*10}")
    for _, r in df_w3.iterrows():
        label = CPC_LABELS.get(r["cpc_section"], r["cpc_section"])
        print(f"  {r['cpc_section']:<5} {label:<28} "
              f"{str(r['company_name'])[:36]:<38} "
              f"{float(r['normalized_score']):>10,.0f}")

    print("\n==========================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("==========================================================\n")

if __name__ == "__main__":
    run_weighted_analysis()