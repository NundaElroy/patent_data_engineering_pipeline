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

def run_company_analysis():
    print("Connecting to database...")
    conn = get_conn()

    # ══════════════════════════════════════════════════════════════════════
    # IBM vs Samsung — Volume vs Quality Over Time
    # Hypothesis: IBM deliberately reduced patent volume while improving
    # citation quality — Samsung did the opposite — proving two completely
    # different innovation philosophies produce measurably different outcomes
    # ══════════════════════════════════════════════════════════════════════
    print("\nRunning IBM vs Samsung: Volume vs Quality Over Time...")
    df_ibm_samsung = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN c.name = 'International Business Machines Corporation'
                THEN 1 ELSE 0 END)                                      AS ibm_patents,
            SUM(CASE WHEN c.name = 'SAMSUNG ELECTRONICS CO., LTD.'
                THEN 1 ELSE 0 END)                                      AS samsung_patents,
            ROUND(AVG(CASE WHEN c.name = 'International Business Machines Corporation'
                THEN pc.citation_count END), 2)                         AS ibm_avg_citations,
            ROUND(AVG(CASE WHEN c.name = 'SAMSUNG ELECTRONICS CO., LTD.'
                THEN pc.citation_count END), 2)                         AS samsung_avg_citations
        FROM patents p
        JOIN relationships r     ON p.patent_id  = r.patent_id
        JOIN companies c         ON r.company_id = c.company_id
        JOIN patent_citations pc ON p.patent_id  = pc.patent_id
        WHERE p.year BETWEEN 1990 AND 2022
          AND c.name IN (
              'International Business Machines Corporation',
              'SAMSUNG ELECTRONICS CO., LTD.'
          )
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Compute IBM citation trend direction
    ibm_early  = df_ibm_samsung[df_ibm_samsung['year'].between(1990, 2000)]['ibm_avg_citations'].mean()
    ibm_late   = df_ibm_samsung[df_ibm_samsung['year'].between(2015, 2019)]['ibm_avg_citations'].mean()
    sam_early  = df_ibm_samsung[df_ibm_samsung['year'].between(1990, 2000)]['samsung_avg_citations'].mean()
    sam_late   = df_ibm_samsung[df_ibm_samsung['year'].between(2015, 2019)]['samsung_avg_citations'].mean()

    ibm_peak_patents = df_ibm_samsung.loc[df_ibm_samsung['ibm_patents'].idxmax(), 'year']
    sam_peak_patents = df_ibm_samsung.loc[df_ibm_samsung['samsung_patents'].idxmax(), 'year']

    # ══════════════════════════════════════════════════════════════════════
    # Query 1: Volume vs Quality Correlation
    # Hypothesis: companies that file more patents produce lower citation
    # quality per patent — proving volume is inversely related to impact
    # ══════════════════════════════════════════════════════════════════════
    print("Running Query 1: Volume vs Quality Correlation (top companies)...")
    df_vol_quality = run_query(conn, """
        SELECT
            c.name,
            COUNT(DISTINCT r.patent_id)      AS total_patents,
            ROUND(AVG(pc.citation_count), 2) AS avg_citations_per_patent,
            SUM(pc.citation_count)           AS total_citations,
            MAX(pc.citation_count)           AS max_patent_citations
        FROM companies c
        JOIN relationships r     ON c.company_id = r.company_id
        JOIN patent_citations pc ON r.patent_id  = pc.patent_id
        WHERE c.name IS NOT NULL
          AND c.name != 'Unknown Company'
        GROUP BY c.company_id, c.name
        HAVING COUNT(DISTINCT r.patent_id) >= 5000
        ORDER BY total_patents DESC
        LIMIT 20;
    """)

    # Compute correlation between volume and quality
    correlation = df_vol_quality['total_patents'].corr(
        df_vol_quality['avg_citations_per_patent']
    )

    # Rank by citations to show who actually leads on quality
    df_vol_quality_by_citations = df_vol_quality.sort_values(
        'avg_citations_per_patent', ascending=False
    ).reset_index(drop=True)

    # ══════════════════════════════════════════════════════════════════════
    # Query 6: Korean vs Chinese Citation Impact in H (Electricity)
    # Hypothesis: as Chinese patent volume in H grew post-2010, Korean
    # average citations per patent declined — proving Chinese flooding
    # degraded citation value of the entire electricity sector
    # ══════════════════════════════════════════════════════════════════════
    print("Running Query 6: KR vs CN Citation Impact in Electricity (H) 2010-2022...")
    df_kr_cn = run_query(conn, """
        SELECT
            p.year,
            ROUND(AVG(CASE WHEN i.country = 'KR'
                THEN pc.citation_count END), 2) AS kr_avg_citations,
            ROUND(AVG(CASE WHEN i.country = 'CN'
                THEN pc.citation_count END), 2) AS cn_avg_citations,
            COUNT(CASE WHEN i.country = 'KR'
                THEN 1 END)                     AS kr_patents,
            COUNT(CASE WHEN i.country = 'CN'
                THEN 1 END)                     AS cn_patents
        FROM patents p
        JOIN cpc_detail cd       ON p.patent_id  = cd.patent_id
        JOIN relationships r     ON p.patent_id  = r.patent_id
        JOIN inventors i         ON r.inventor_id = i.inventor_id
        JOIN patent_citations pc ON p.patent_id   = pc.patent_id
        WHERE cd.cpc_section = 'H'
          AND p.year BETWEEN 2010 AND 2022
          AND i.country IN ('KR', 'CN')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Compute correlation between CN volume and KR citations
    kr_cn_correlation = df_kr_cn['cn_patents'].corr(df_kr_cn['kr_avg_citations'])

    conn.close()

    # ── CSV Exports ───────────────────────────────────────────────────────
    print("\nExporting CSVs...")
    df_ibm_samsung.to_csv(          f"{OUTPUT_DIR}/company_ibm_vs_samsung.csv",        index=False)
    df_vol_quality.to_csv(          f"{OUTPUT_DIR}/company_volume_vs_quality.csv",      index=False)
    df_vol_quality_by_citations.to_csv(f"{OUTPUT_DIR}/company_quality_ranking.csv",     index=False)
    df_kr_cn.to_csv(                f"{OUTPUT_DIR}/company_kr_vs_cn_citations.csv",     index=False)

    # ── JSON Export ───────────────────────────────────────────────────────
    print("Writing company analysis JSON...")
    report = {
        "ibm_vs_samsung"                  : df_ibm_samsung.to_dict(orient="records"),
        "ibm_peak_patent_year"            : int(ibm_peak_patents),
        "samsung_peak_patent_year"        : int(sam_peak_patents),
        "ibm_avg_citations_1990_2000"     : round(float(ibm_early), 2),
        "ibm_avg_citations_2015_2019"     : round(float(ibm_late),  2),
        "samsung_avg_citations_1990_2000" : round(float(sam_early), 2),
        "samsung_avg_citations_2015_2019" : round(float(sam_late),  2),
        "volume_vs_quality"               : df_vol_quality.to_dict(orient="records"),
        "quality_ranking"                 : df_vol_quality_by_citations.to_dict(orient="records"),
        "volume_quality_correlation"      : round(float(correlation), 4),
        "kr_vs_cn_citations"              : df_kr_cn.to_dict(orient="records"),
        "kr_cn_correlation"               : round(float(kr_cn_correlation), 4),
    }
    with open(f"{OUTPUT_DIR}/company_report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    # ── Console Report ────────────────────────────────────────────────────
    print("\n============== COMPANY DIAGNOSTIC REPORT ==============")

    # IBM vs Samsung
    print("\n  IBM vs Samsung — Volume vs Citation Quality Over Time")
    print(f"  IBM peak patent year:     {int(ibm_peak_patents)}")
    print(f"  Samsung peak patent year: {int(sam_peak_patents)}")
    print(f"  IBM avg citations 1990-2000:    {ibm_early:.2f} per patent")
    print(f"  IBM avg citations 2015-2019:    {ibm_late:.2f} per patent")
    ibm_direction = "IMPROVED" if ibm_late > ibm_early else "DECLINED"
    print(f"  IBM citation quality {ibm_direction} as volume changed")
    print(f"  Samsung avg citations 1990-2000: {sam_early:.2f} per patent")
    print(f"  Samsung avg citations 2015-2019: {sam_late:.2f} per patent")
    sam_direction = "IMPROVED" if sam_late > sam_early else "DECLINED"
    print(f"  Samsung citation quality {sam_direction} as volume grew")
    print(f"\n  {'Year':<6} {'IBM Patents':>12} {'IBM Avg Cite':>13} {'SAM Patents':>12} {'SAM Avg Cite':>13}")
    print(f"  {'-'*6} {'-'*12} {'-'*13} {'-'*12} {'-'*13}")
    milestones = [1990, 1995, 2000, 2005, 2010, 2015, 2018, 2020, 2022]
    for _, r in df_ibm_samsung[df_ibm_samsung['year'].isin(milestones)].iterrows():
        ibm_c = f"{float(r['ibm_avg_citations']):>13.1f}" if pd.notna(r['ibm_avg_citations']) else "          N/A"
        sam_c = f"{float(r['samsung_avg_citations']):>13.1f}" if pd.notna(r['samsung_avg_citations']) else "          N/A"
        print(f"  {int(r['year']):<6} {int(r['ibm_patents']):>12,} {ibm_c} "
              f"{int(r['samsung_patents']):>12,} {sam_c}")

    # Volume vs Quality
    print(f"\n  Query 1: Volume vs Citation Quality Correlation")
    print(f"  Correlation coefficient: {correlation:.4f}")
    if correlation < -0.3:
        print("  *** Negative correlation confirmed — more patents = lower quality per patent ***")
    elif correlation > 0.3:
        print("  Positive correlation — larger companies maintain quality at scale")
    else:
        print("  Weak correlation — volume and quality are independent")

    print(f"\n  Ranked by Volume (descending):")
    print(f"  {'Rank':<5} {'Company':<45} {'Patents':>8} {'Avg Citations':>13}")
    print(f"  {'-'*5} {'-'*45} {'-'*8} {'-'*13}")
    for i, r in df_vol_quality.iterrows():
        print(f"  {i+1:<5} {str(r['name'])[:43]:<45} "
              f"{int(r['total_patents']):>8,} "
              f"{float(r['avg_citations_per_patent']):>13.2f}")

    print(f"\n  Ranked by Citation Quality (descending):")
    print(f"  {'Rank':<5} {'Company':<45} {'Patents':>8} {'Avg Citations':>13}")
    print(f"  {'-'*5} {'-'*45} {'-'*8} {'-'*13}")
    for i, r in df_vol_quality_by_citations.iterrows():
        print(f"  {i+1:<5} {str(r['name'])[:43]:<45} "
              f"{int(r['total_patents']):>8,} "
              f"{float(r['avg_citations_per_patent']):>13.2f}")

    # KR vs CN
    print(f"\n  Query 6: Korea vs China Citation Impact in Electricity (H)")
    print(f"  Correlation — CN patent volume vs KR avg citations: {kr_cn_correlation:.4f}")
    if kr_cn_correlation < -0.5:
        print("  *** Strong negative correlation — Chinese flooding degraded Korean citation value ***")
    elif kr_cn_correlation < -0.3:
        print("  Moderate negative correlation — partial degradation effect confirmed")
    else:
        print("  Weak correlation — Chinese growth did not measurably hurt Korean citation quality")
    print(f"\n  {'Year':<6} {'KR Avg Cite':>12} {'CN Avg Cite':>12} {'KR Patents':>11} {'CN Patents':>11}")
    print(f"  {'-'*6} {'-'*12} {'-'*12} {'-'*11} {'-'*11}")
    for _, r in df_kr_cn.iterrows():
        kr_c = f"{float(r['kr_avg_citations']):>12.2f}" if pd.notna(r['kr_avg_citations']) else "         N/A"
        cn_c = f"{float(r['cn_avg_citations']):>12.2f}" if pd.notna(r['cn_avg_citations']) else "         N/A"
        print(f"  {int(r['year']):<6} {kr_c} {cn_c} "
              f"{int(r['kr_patents']):>11,} {int(r['cn_patents']):>11,}")

    print("\n=======================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("=======================================================\n")

if __name__ == "__main__":
    run_company_analysis()