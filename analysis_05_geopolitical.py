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

def run_geopolitical_analysis():
    print("Connecting to database...")
    conn = get_conn()

    # G1: USA vs China Overall Patent Growth
    # Hypothesis: China transformed from manufacturing follower to
    # innovation competitor — visible as share crossover post-2010
    print("\nRunning G1: USA vs China Overall Patent Growth...")
    df_g1 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN i.country = 'US' THEN 1 ELSE 0 END) AS us_patents,
            SUM(CASE WHEN i.country = 'CN' THEN 1 ELSE 0 END) AS cn_patents,
            SUM(CASE WHEN i.country = 'JP' THEN 1 ELSE 0 END) AS jp_patents,
            SUM(CASE WHEN i.country = 'KR' THEN 1 ELSE 0 END) AS kr_patents,
            SUM(CASE WHEN i.country = 'DE' THEN 1 ELSE 0 END) AS de_patents
        FROM patents p
        JOIN relationships r ON p.patent_id  = r.patent_id
        JOIN inventors i     ON r.inventor_id = i.inventor_id
        WHERE p.year BETWEEN 1990 AND 2022
          AND i.country IN ('US', 'CN', 'JP', 'KR', 'DE')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Compute US and CN share of combined top-5 per year
    df_g1['total'] = (df_g1['us_patents'] + df_g1['cn_patents'] +
                      df_g1['jp_patents'] + df_g1['kr_patents'] + df_g1['de_patents'])
    df_g1['us_share_pct'] = (df_g1['us_patents'] / df_g1['total'] * 100).round(2)
    df_g1['cn_share_pct'] = (df_g1['cn_patents'] / df_g1['total'] * 100).round(2)

    # G2: Trade War Effect on H01L Semiconductors
    # Hypothesis: 2018 US sanctions caused Chinese H01L patents to
    # initially slow then spike as China scrambled for self-sufficiency
    # while US share held steady — proving sanctions backfired
    print("Running G2: Trade War Effect on Semiconductor Patents (H01L)...")
    df_g2 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN i.country = 'US' THEN 1 ELSE 0 END) AS us_h01l,
            SUM(CASE WHEN i.country = 'CN' THEN 1 ELSE 0 END) AS cn_h01l,
            SUM(CASE WHEN i.country = 'KR' THEN 1 ELSE 0 END) AS kr_h01l,
            SUM(CASE WHEN i.country = 'TW' THEN 1 ELSE 0 END) AS tw_h01l,
            SUM(CASE WHEN i.country = 'JP' THEN 1 ELSE 0 END) AS jp_h01l
        FROM patents p
        JOIN cpc_detail cd   ON p.patent_id  = cd.patent_id
        JOIN relationships r ON p.patent_id  = r.patent_id
        JOIN inventors i     ON r.inventor_id = i.inventor_id
        WHERE cd.cpc_subclass = 'H01L'
          AND p.year BETWEEN 2010 AND 2022
          AND i.country IN ('US', 'CN', 'KR', 'TW', 'JP')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # G3: Korea vs Japan Semiconductor Displacement (H01L)
    # Hypothesis: Korea's H01L growth directly displaced Japan patent
    # for patent — zero-sum competition not market expansion
    # Proof: correlation coefficient between JP decline and KR rise
    print("Running G3: Korea vs Japan Semiconductor Displacement (H01L)...")
    df_g3 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN i.country = 'JP' THEN 1 ELSE 0 END) AS jp_h01l,
            SUM(CASE WHEN i.country = 'KR' THEN 1 ELSE 0 END) AS kr_h01l,
            COUNT(DISTINCT p.patent_id)                        AS total_h01l
        FROM patents p
        JOIN cpc_detail cd   ON p.patent_id  = cd.patent_id
        JOIN relationships r ON p.patent_id  = r.patent_id
        JOIN inventors i     ON r.inventor_id = i.inventor_id
        WHERE cd.cpc_subclass = 'H01L'
          AND p.year BETWEEN 1985 AND 2022
          AND i.country IN ('JP', 'KR')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Compute shares and correlation
    df_g3['jp_share_pct'] = (df_g3['jp_h01l'] / df_g3['total_h01l'] * 100).round(2)
    df_g3['kr_share_pct'] = (df_g3['kr_h01l'] / df_g3['total_h01l'] * 100).round(2)
    correlation = df_g3['jp_share_pct'].corr(df_g3['kr_share_pct'])

    conn.close()

    #CSV Exports
    print("\nExporting CSVs...")
    df_g1.to_csv(f"{OUTPUT_DIR}/geo_us_vs_china_overall.csv",        index=False)
    df_g2.to_csv(f"{OUTPUT_DIR}/geo_trade_war_semiconductors.csv",   index=False)
    df_g3.to_csv(f"{OUTPUT_DIR}/geo_korea_vs_japan_h01l.csv",        index=False)

    #JSON Export
    print("Writing geopolitical diagnostics JSON...")
    report = {
        "geo_us_vs_china_overall"      : df_g1.to_dict(orient="records"),
        "geo_trade_war_semiconductors" : df_g2.to_dict(orient="records"),
        "geo_korea_vs_japan_h01l"      : df_g3.to_dict(orient="records"),
        "geo_korea_japan_correlation"  : round(correlation, 4),
    }
    with open(f"{OUTPUT_DIR}/geopolitical_report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    #Console Report    print("\n======== SECTION 3: GEOPOLITICAL DIAGNOSTICS ========")

    # G1
    print("\n  G1: USA vs China — Patent Share Over Time")
    cn_crossover = df_g1[df_g1['cn_patents'] > df_g1['us_patents']]
    if not cn_crossover.empty:
        print(f"  *** Crossover: {int(cn_crossover.iloc[0]['year'])} — China overtook US in raw patent count ***")
    else:
        print("  No raw count crossover yet — check share trend below")
    print(f"  {'Year':<6} {'US':>8} {'CN':>8} {'JP':>8} {'KR':>8} {'US Share':>10} {'CN Share':>10}")
    print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*10}")
    milestones = [1990, 1995, 2000, 2001, 2005, 2010, 2015, 2018, 2020, 2022]
    for _, r in df_g1[df_g1['year'].isin(milestones)].iterrows():
        marker = " <- WTO" if int(r['year']) == 2001 else ""
        marker = " <- MIC2025" if int(r['year']) == 2015 else marker
        print(f"  {int(r['year']):<6} {int(r['us_patents']):>8,} {int(r['cn_patents']):>8,} "
              f"{int(r['jp_patents']):>8,} {int(r['kr_patents']):>8,} "
              f"{float(r['us_share_pct']):>9.1f}% {float(r['cn_share_pct']):>9.1f}%{marker}")

    # G2
    print("\n  G2: Trade War Effect — H01L Semiconductors by Country (2010-2022)")
    print("  Diagnostic: did Chinese H01L patents slow after 2018 then spike?")
    print(f"  {'Year':<6} {'US':>8} {'CN':>8} {'KR':>8} {'TW':>8} {'JP':>8}")
    print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for _, r in df_g2.iterrows():
        marker = " <- Sanctions" if int(r['year']) == 2018 else ""
        print(f"  {int(r['year']):<6} {int(r['us_h01l']):>8,} {int(r['cn_h01l']):>8,} "
              f"{int(r['kr_h01l']):>8,} {int(r['tw_h01l']):>8,} "
              f"{int(r['jp_h01l']):>8,}{marker}")

    # G3
    print("\n  G3: Korea vs Japan — H01L Semiconductor Displacement")
    print(f"  Correlation coefficient JP decline vs KR rise: {correlation:.4f}")
    if correlation < -0.7:
        print("  *** Strong negative correlation — Korea's rise directly displaced Japan ***")
    elif correlation < -0.4:
        print("  Moderate negative correlation — partial displacement confirmed")
    else:
        print("  Weak correlation — market expansion, not pure displacement")
    print(f"  {'Year':<6} {'JP H01L':>10} {'KR H01L':>10} {'JP Share':>10} {'KR Share':>10}")
    print(f"  {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    milestones = [1985, 1990, 1995, 2000, 2005, 2008, 2010, 2015, 2020, 2022]
    for _, r in df_g3[df_g3['year'].isin(milestones)].iterrows():
        print(f"  {int(r['year']):<6} {int(r['jp_h01l']):>10,} {int(r['kr_h01l']):>10,} "
              f"{float(r['jp_share_pct']):>9.1f}% {float(r['kr_share_pct']):>9.1f}%")

    print("\n=====================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("=====================================================\n")

if __name__ == "__main__":
    run_geopolitical_analysis()