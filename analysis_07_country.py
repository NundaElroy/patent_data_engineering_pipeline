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

# Policy events to annotate on China chart
CHINA_EVENTS = {
    1985: "Patent Law enacted",
    1992: "Patent Law amended",
    2001: "WTO accession",
    2008: "Patent Law strengthened",
    2015: "Made in China 2025",
    2018: "US-China trade war",
}

def run_country_analysis():
    print("Connecting to database...")
    conn = get_conn()

    # C1: China Patent Growth Over Time
    # Hypothesis: Chinese patent growth follows policy interventions
    # not organic innovation — WTO 2001 and MIC2025 are inflection points
    print("\nRunning C1: China Patent Growth Over Time...")
    df_c1 = run_query(conn, """
        SELECT
            p.year,
            COUNT(DISTINCT p.patent_id)                                AS total_patents,
            SUM(CASE WHEN i.country = 'CN' THEN 1 ELSE 0 END)         AS cn_patents,
            SUM(CASE WHEN i.country = 'US' THEN 1 ELSE 0 END)         AS us_patents,
            SUM(CASE WHEN i.country = 'JP' THEN 1 ELSE 0 END)         AS jp_patents,
            SUM(CASE WHEN i.country = 'KR' THEN 1 ELSE 0 END)         AS kr_patents,
            SUM(CASE WHEN i.country = 'DE' THEN 1 ELSE 0 END)         AS de_patents
        FROM patents p
        JOIN relationships r ON p.patent_id  = r.patent_id
        JOIN inventors i     ON r.inventor_id = i.inventor_id
        WHERE p.year BETWEEN 1985 AND 2022
          AND i.country IN ('CN', 'US', 'JP', 'KR', 'DE')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Compute China share and growth rate
    df_c1['cn_share_pct']  = (df_c1['cn_patents'] / df_c1['total_patents'] * 100).round(2)
    df_c1['us_share_pct']  = (df_c1['us_patents'] / df_c1['total_patents'] * 100).round(2)
    df_c1['cn_growth_pct'] = df_c1['cn_patents'].pct_change().mul(100).round(2)

    # Pre vs post WTO comparison
    pre_wto  = df_c1[df_c1['year'].between(1995, 2000)]['cn_patents'].mean()
    post_wto = df_c1[df_c1['year'].between(2002, 2007)]['cn_patents'].mean()
    pre_mic  = df_c1[df_c1['year'].between(2010, 2014)]['cn_patents'].mean()
    post_mic = df_c1[df_c1['year'].between(2016, 2020)]['cn_patents'].mean()

    wto_multiplier = round(post_wto / pre_wto, 2)  if pre_wto  > 0 else None
    mic_multiplier = round(post_mic / pre_mic, 2)   if pre_mic  > 0 else None

    # C2: Top Country Per CPC Section
    # Which country dominates each technology area
    # Reveals national specialization — DE in mechanical, US in computing
    print("Running C2: Top Country Per CPC Section...")
    df_c2 = run_query(conn, """
        WITH CountrySection AS (
            SELECT
                i.country,
                c.cpc_section,
                COUNT(DISTINCT p.patent_id)  AS patents,
                RANK() OVER (
                    PARTITION BY c.cpc_section
                    ORDER BY COUNT(DISTINCT p.patent_id) DESC
                ) AS rnk
            FROM patents p
            JOIN cpc c           ON p.patent_id  = c.patent_id
            JOIN relationships r ON p.patent_id  = r.patent_id
            JOIN inventors i     ON r.inventor_id = i.inventor_id
            WHERE i.country IS NOT NULL
              AND i.country NOT IN ('Unknown', '')
              AND c.cpc_section IS NOT NULL
              AND p.year BETWEEN 1976 AND 2022
            GROUP BY i.country, c.cpc_section
        )
        SELECT country, cpc_section, patents
        FROM CountrySection
        WHERE rnk = 1
        ORDER BY patents DESC;
    """)
    df_c2['cpc_label'] = df_c2['cpc_section'].map(CPC_LABELS)

    # Also get top 3 per section for richer context
    df_c2_top3 = run_query(conn, """
        WITH CountrySection AS (
            SELECT
                i.country,
                c.cpc_section,
                COUNT(DISTINCT p.patent_id)  AS patents,
                RANK() OVER (
                    PARTITION BY c.cpc_section
                    ORDER BY COUNT(DISTINCT p.patent_id) DESC
                ) AS rnk
            FROM patents p
            JOIN cpc c           ON p.patent_id  = c.patent_id
            JOIN relationships r ON p.patent_id  = r.patent_id
            JOIN inventors i     ON r.inventor_id = i.inventor_id
            WHERE i.country IS NOT NULL
              AND i.country NOT IN ('Unknown', '')
              AND c.cpc_section IS NOT NULL
              AND p.year BETWEEN 1976 AND 2022
            GROUP BY i.country, c.cpc_section
        )
        SELECT country, cpc_section, patents, rnk
        FROM CountrySection
        WHERE rnk <= 3
        ORDER BY cpc_section ASC, rnk ASC;
    """)
    df_c2_top3['cpc_label'] = df_c2_top3['cpc_section'].map(CPC_LABELS)

    # C3: Country Innovation Efficiency
    # Patents vs average citations per patent per country
    # Reveals quality vs quantity tradeoff
    # High volume low citation = subsidy driven filing (China, KR)
    # Low volume high citation = quality driven filing (CH, IL)
    print("Running C3: Country Innovation Efficiency (citations vs volume)...")
    df_c3 = run_query(conn, """
        SELECT
            i.country,
            COUNT(DISTINCT p.patent_id)          AS total_patents,
            SUM(pc.citation_count)               AS total_citations,
            ROUND(AVG(pc.citation_count), 2)     AS avg_citations_per_patent,
            MAX(pc.citation_count)               AS max_citations
        FROM patents p
        JOIN relationships r     ON p.patent_id  = r.patent_id
        JOIN inventors i         ON r.inventor_id = i.inventor_id
        JOIN patent_citations pc ON p.patent_id  = pc.patent_id
        WHERE i.country IS NOT NULL
          AND i.country NOT IN ('Unknown', '')
          AND p.year BETWEEN 1976 AND 2019
        GROUP BY i.country
        HAVING COUNT(DISTINCT p.patent_id) >= 1000
        ORDER BY total_patents DESC
        LIMIT 30;
    """)

    # Classify countries into quadrants
    median_vol  = df_c3['total_patents'].median()
    median_qual = df_c3['avg_citations_per_patent'].median()

    def quadrant(row):
        high_vol  = row['total_patents']          > median_vol
        high_qual = row['avg_citations_per_patent'] > median_qual
        if high_vol  and high_qual:  return "High Volume High Quality"
        if high_vol  and not high_qual: return "High Volume Low Quality"
        if not high_vol and high_qual:  return "Low Volume High Quality"
        return "Low Volume Low Quality"

    df_c3['quadrant'] = df_c3.apply(quadrant, axis=1)

    conn.close()

    # ── CSV Exports ───────────────────────────────────────────────────────
    print("\nExporting CSVs...")
    df_c1.to_csv(      f"{OUTPUT_DIR}/country_china_growth.csv",        index=False)
    df_c2.to_csv(      f"{OUTPUT_DIR}/country_top_per_section.csv",     index=False)
    df_c2_top3.to_csv( f"{OUTPUT_DIR}/country_top3_per_section.csv",    index=False)
    df_c3.to_csv(      f"{OUTPUT_DIR}/country_innovation_efficiency.csv", index=False)

    # ── JSON Export ───────────────────────────────────────────────────────
    print("Writing country analysis JSON...")
    report = {
        "country_china_growth"          : df_c1.to_dict(orient="records"),
        "country_china_events"          : CHINA_EVENTS,
        "country_china_wto_multiplier"  : wto_multiplier,
        "country_china_mic_multiplier"  : mic_multiplier,
        "country_top_per_section"       : df_c2.to_dict(orient="records"),
        "country_top3_per_section"      : df_c2_top3.to_dict(orient="records"),
        "country_innovation_efficiency" : df_c3.to_dict(orient="records"),
    }
    with open(f"{OUTPUT_DIR}/country_report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    # ── Console Report ────────────────────────────────────────────────────
    print("\n============== COUNTRY ANALYSIS REPORT ==============")

    # C1
    print("\n  C1: China Patent Growth Over Time")
    print(f"  Average patents per year 1995-2000 (pre-WTO):    {int(pre_wto):,}")
    print(f"  Average patents per year 2002-2007 (post-WTO):   {int(post_wto):,}")
    print(f"  WTO multiplier: {wto_multiplier}x growth after accession")
    print(f"  Average patents per year 2010-2014 (pre-MIC25):  {int(pre_mic):,}")
    print(f"  Average patents per year 2016-2020 (post-MIC25): {int(post_mic):,}")
    print(f"  MIC2025 multiplier: {mic_multiplier}x growth after policy launch")
    print(f"\n  {'Year':<6} {'CN':>8} {'US':>8} {'JP':>8} {'KR':>8} {'DE':>8} {'CN Share':>9}  Event")
    print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*9}  {'-'*25}")
    milestones = [1985, 1990, 1995, 2001, 2005, 2008, 2010, 2015, 2018, 2020, 2022]
    for _, r in df_c1[df_c1['year'].isin(milestones)].iterrows():
        event = CHINA_EVENTS.get(int(r['year']), "")
        print(f"  {int(r['year']):<6} {int(r['cn_patents']):>8,} {int(r['us_patents']):>8,} "
              f"{int(r['jp_patents']):>8,} {int(r['kr_patents']):>8,} "
              f"{int(r['de_patents']):>8,} {float(r['cn_share_pct']):>8.1f}%  {event}")

    # C2
    print("\n  C2: Top Country Per CPC Technology Section")
    print(f"  {'Section':<5} {'Label':<28} {'Country':<8} {'Patents':>10}")
    print(f"  {'-'*5} {'-'*28} {'-'*8} {'-'*10}")
    for _, r in df_c2.iterrows():
        print(f"  {r['cpc_section']:<5} {str(r['cpc_label']):<28} "
              f"{r['country']:<8} {int(r['patents']):>10,}")

    print("\n  Top 3 Countries Per Section:")
    current_section = None
    for _, r in df_c2_top3.iterrows():
        if r['cpc_section'] != current_section:
            current_section = r['cpc_section']
            label = CPC_LABELS.get(r['cpc_section'], r['cpc_section'])
            print(f"\n  {r['cpc_section']} — {label}")
        print(f"    {int(r['rnk'])}. {r['country']:<6} {int(r['patents']):>10,}")

    # C3
    print("\n  C3: Country Innovation Efficiency (Volume vs Citation Quality)")
    print(f"  {'Country':<8} {'Patents':>10} {'Avg Citations':>14} {'Quadrant':<30}")
    print(f"  {'-'*8} {'-'*10} {'-'*14} {'-'*30}")
    for _, r in df_c3.head(20).iterrows():
        print(f"  {r['country']:<8} {int(r['total_patents']):>10,} "
              f"{float(r['avg_citations_per_patent']):>14.2f} "
              f"{r['quadrant']:<30}")

    print("\n=====================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("=====================================================\n")

if __name__ == "__main__":
    run_country_analysis()