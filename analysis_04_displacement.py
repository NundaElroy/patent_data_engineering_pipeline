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

def find_crossover(df, col_a, col_b):
    """Return first year where col_a overtakes col_b."""
    cross = df[df[col_a] > df[col_b]]
    return int(cross.iloc[0]['year']) if not cross.empty else None

def run_displacement_analysis():
    print("Connecting to database...")
    conn = get_conn()

    # D1: Smartphones vs Traditional Telephony (H04W vs H04M)
    # Hypothesis: wireless patents overtook wired telephony patents
    # after iPhone launch (2007) proving mobile displaced fixed-line innovation
    print("\nRunning D1: Smartphones vs Traditional Telephony (H04W vs H04M)...")
    df_d1 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'H04W' THEN 1 ELSE 0 END) AS wireless_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'H04M' THEN 1 ELSE 0 END) AS telephony_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1990 AND 2022
          AND cd.cpc_subclass IN ('H04W', 'H04M')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # D2: Electric Vehicles vs Internal Combustion Engines (B60L vs F02D/F02M)
    # Hypothesis: EV patents overtook combustion engine patents post-2015
    # Paris Agreement and Tesla growth as the trigger
    print("Running D2: Electric Vehicles vs Combustion Engines (B60L vs F02D/F02M)...")
    df_d2 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'B60L' THEN 1 ELSE 0 END)                  AS ev_patents,
            SUM(CASE WHEN cd.cpc_subclass IN ('F02D', 'F02M') THEN 1 ELSE 0 END)        AS combustion_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1990 AND 2022
          AND cd.cpc_subclass IN ('B60L', 'F02D', 'F02M')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # D3: AI vs Traditional Software (G06N vs G06F)
    # Hypothesis: AI patents grew as a rising share of all computing patents
    # post-2012 (AlexNet moment) proving ML transformed software innovation
    # Note: crossover is in growth RATE not absolute count
    print("Running D3: AI Patents vs Traditional Software (G06N vs G06F)...")
    df_d3 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'G06N' THEN 1 ELSE 0 END) AS ai_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'G06F' THEN 1 ELSE 0 END) AS software_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1990 AND 2022
          AND cd.cpc_subclass IN ('G06N', 'G06F')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Compute AI share of total computing patents per year
    df_d3['total_computing'] = df_d3['ai_patents'] + df_d3['software_patents']
    df_d3['ai_share_pct'] = (
        df_d3['ai_patents'] / df_d3['total_computing'] * 100
    ).round(2)

    # D4: Clean Energy vs Fossil Fuel Technologies (Y02E vs F02+C10)
    # Hypothesis: clean energy patents accelerated sharply after
    # Paris Agreement (2015) while fossil fuel innovation stalled
    # proving policy drives innovation more than technology readiness
    print("Running D4: Clean Energy vs Fossil Fuel (Y02E vs F02+C10)...")
    df_d4 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'Y02E' THEN 1 ELSE 0 END)       AS clean_energy_patents,
            SUM(CASE WHEN cd.cpc_subclass LIKE 'F02%'
                      OR cd.cpc_subclass LIKE 'C10%' THEN 1 ELSE 0 END)      AS fossil_fuel_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1990 AND 2022
          AND (cd.cpc_subclass = 'Y02E'
               OR cd.cpc_subclass LIKE 'F02%'
               OR cd.cpc_subclass LIKE 'C10%')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    conn.close()

    # ── CSV Exports ───────────────────────────────────────────────────────
    print("\nExporting CSVs...")
    df_d1.to_csv(f"{OUTPUT_DIR}/diag_smartphones_vs_telephony.csv", index=False)
    df_d2.to_csv(f"{OUTPUT_DIR}/diag_ev_vs_combustion.csv",         index=False)
    df_d3.to_csv(f"{OUTPUT_DIR}/diag_ai_vs_software.csv",           index=False)
    df_d4.to_csv(f"{OUTPUT_DIR}/diag_clean_vs_fossil.csv",          index=False)

    # ── JSON Export ───────────────────────────────────────────────────────
    print("Writing displacement diagnostics JSON...")
    report = {
        "diag_smartphones_vs_telephony" : df_d1.to_dict(orient="records"),
        "diag_ev_vs_combustion"         : df_d2.to_dict(orient="records"),
        "diag_ai_vs_software"           : df_d3.to_dict(orient="records"),
        "diag_clean_vs_fossil"          : df_d4.to_dict(orient="records"),
    }
    with open(f"{OUTPUT_DIR}/displacement_report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    # ── Console Report ────────────────────────────────────────────────────
    print("\n======== SECTION 2: DISPLACEMENT DIAGNOSTICS ========")

    # D1
    print("\n  D1: Smartphones vs Traditional Telephony (H04W vs H04M)")
    crossover = find_crossover(df_d1, 'wireless_patents', 'telephony_patents')
    if crossover:
        print(f"  *** Crossover year: {crossover} — wireless overtook wired telephony ***")
    else:
        print("  No crossover detected in dataset range")
    print(f"  {'Year':<6} {'Wireless H04W':>14} {'Telephony H04M':>15}")
    print(f"  {'-'*6} {'-'*14} {'-'*15}")
    milestones = [1995, 2000, 2005, 2007, 2010, 2015, 2019, 2022]
    for _, r in df_d1[df_d1['year'].isin(milestones)].iterrows():
        marker = " <- iPhone launch" if int(r['year']) == 2007 else ""
        print(f"  {int(r['year']):<6} {int(r['wireless_patents']):>14,} "
              f"{int(r['telephony_patents']):>15,}{marker}")

    # D2
    print("\n  D2: Electric Vehicles vs Combustion Engines (B60L vs F02D/F02M)")
    crossover = find_crossover(df_d2, 'ev_patents', 'combustion_patents')
    if crossover:
        print(f"  *** Crossover year: {crossover} — EV overtook combustion patents ***")
    else:
        print("  No crossover yet — combustion still leads in dataset range")
    print(f"  {'Year':<6} {'EV B60L':>10} {'Combustion':>12}")
    print(f"  {'-'*6} {'-'*10} {'-'*12}")
    milestones = [1995, 2000, 2005, 2010, 2015, 2016, 2018, 2020, 2022]
    for _, r in df_d2[df_d2['year'].isin(milestones)].iterrows():
        marker = " <- Paris Agreement" if int(r['year']) == 2015 else ""
        print(f"  {int(r['year']):<6} {int(r['ev_patents']):>10,} "
              f"{int(r['combustion_patents']):>12,}{marker}")

    # D3
    print("\n  D3: AI Patents vs Traditional Software (G06N vs G06F)")
    print("  Diagnostic: AI share of all computing patents rising post-2012")
    print(f"  {'Year':<6} {'AI G06N':>10} {'Software G06F':>14} {'AI Share':>10}")
    print(f"  {'-'*6} {'-'*10} {'-'*14} {'-'*10}")
    milestones = [1995, 2000, 2005, 2010, 2012, 2015, 2017, 2019, 2021, 2022]
    for _, r in df_d3[df_d3['year'].isin(milestones)].iterrows():
        marker = " <- AlexNet" if int(r['year']) == 2012 else ""
        print(f"  {int(r['year']):<6} {int(r['ai_patents']):>10,} "
              f"{int(r['software_patents']):>14,} "
              f"{float(r['ai_share_pct']):>9.1f}%{marker}")

    # D4
    print("\n  D4: Clean Energy vs Fossil Fuel (Y02E vs F02+C10)")
    crossover = find_crossover(df_d4, 'clean_energy_patents', 'fossil_fuel_patents')
    if crossover:
        print(f"  *** Crossover year: {crossover} — clean energy overtook fossil fuel patents ***")
    else:
        print("  No crossover yet in dataset range")
    print(f"  {'Year':<6} {'Clean Y02E':>12} {'Fossil F02+C10':>15}")
    print(f"  {'-'*6} {'-'*12} {'-'*15}")
    milestones = [1995, 1997, 2000, 2005, 2010, 2015, 2016, 2019, 2022]
    for _, r in df_d4[df_d4['year'].isin(milestones)].iterrows():
        marker = " <- Paris Agreement" if int(r['year']) == 2015 else ""
        marker = " <- Kyoto Protocol"  if int(r['year']) == 1997 else marker
        print(f"  {int(r['year']):<6} {int(r['clean_energy_patents']):>12,} "
              f"{int(r['fossil_fuel_patents']):>15,}{marker}")

    print("\n=====================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("=====================================================\n")

if __name__ == "__main__":
    run_displacement_analysis()