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

def find_peak(df, col):
    """Return year where col is maximum."""
    idx = df[col].idxmax()
    return int(df.loc[idx, 'year'])

def find_inflection(df, col):
    """Return year of maximum year-over-year growth rate."""
    df = df.copy()
    df['growth'] = df[col].pct_change() * 100
    idx = df['growth'].idxmax()
    return int(df.loc[idx, 'year'])

def compute_multiplier(df, col, pre_start, pre_end, post_start, post_end):
    pre  = df[df['year'].between(pre_start,  pre_end)][col].mean()
    post = df[df['year'].between(post_start, post_end)][col].mean()
    return round(post / pre, 2) if pre > 0 else None

def run_media_energy_analysis():
    print("Connecting to database...")
    conn = get_conn()

    # 
    # TREND 1: Death of Physical Media — Streaming vs Optical Discs
    # Legacy:   G11B (optical recording — DVDs, CDs, Blu-rays)
    # Emerging: H04L (network transmission — streaming protocols)
    # Hypothesis: optical disc patents show a mountain peak that crashes
    # after 2008 while streaming shows a vertical hockey stick
    # Netflix launched streaming 2007 — mark as intervention point
    # 
    print("\nRunning Trend 1: Death of Physical Media (Streaming vs Optical Discs)...")
    df_media = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'G11B'
                THEN 1 ELSE 0 END)          AS optical_disc_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'H04L'
                THEN 1 ELSE 0 END)          AS streaming_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1995 AND 2022
          AND cd.cpc_subclass IN ('G11B', 'H04L')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    df_media['optical_growth']   = df_media['optical_disc_patents'].pct_change().mul(100).round(2)
    df_media['streaming_growth'] = df_media['streaming_patents'].pct_change().mul(100).round(2)

    optical_peak       = find_peak(df_media, 'optical_disc_patents')
    streaming_inflect  = find_inflection(df_media, 'streaming_patents')
    crossover_media    = find_crossover(df_media, 'streaming_patents', 'optical_disc_patents')

    # Pre vs post Netflix streaming launch 2007
    optical_pre  = compute_multiplier(df_media, 'optical_disc_patents', 2002, 2006, 2009, 2014)
    stream_multi = compute_multiplier(df_media, 'streaming_patents',    2002, 2006, 2009, 2014)

    # 
    # TREND 2: Renewables vs Fossil Fuel Extraction
    # Legacy:   E21B (earth drilling — oil, gas, water extraction)
    # Emerging: H02S (solar photovoltaic power generation)
    #           F03D (wind motors / wind turbines)
    # Hypothesis: E21B stays flat as mature field while H02S shows
    # exponential takeoff starting 2010-2011
    # Key annotation: 2011 is when solar PV patents separated from fossil R&D
    # 
    print("Running Trend 2: Renewables vs Fossil Fuel Extraction (E21B vs H02S + F03D)...")
    df_energy = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'E21B'
                THEN 1 ELSE 0 END)          AS fossil_extraction_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'H02S'
                THEN 1 ELSE 0 END)          AS solar_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'F03D'
                THEN 1 ELSE 0 END)          AS wind_patents,
            SUM(CASE WHEN cd.cpc_subclass IN ('H02S', 'F03D')
                THEN 1 ELSE 0 END)          AS total_renewable_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1995 AND 2022
          AND cd.cpc_subclass IN ('E21B', 'H02S', 'F03D')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    df_energy['fossil_growth']    = df_energy['fossil_extraction_patents'].pct_change().mul(100).round(2)
    df_energy['solar_growth']     = df_energy['solar_patents'].pct_change().mul(100).round(2)
    df_energy['wind_growth']      = df_energy['wind_patents'].pct_change().mul(100).round(2)
    df_energy['renewable_growth'] = df_energy['total_renewable_patents'].pct_change().mul(100).round(2)

    solar_inflect     = find_inflection(df_energy, 'solar_patents')
    crossover_energy  = find_crossover(df_energy, 'total_renewable_patents', 'fossil_extraction_patents')
    fossil_peak       = find_peak(df_energy, 'fossil_extraction_patents')

    # Pre vs post Paris Agreement 2015
    fossil_multi  = compute_multiplier(df_energy, 'fossil_extraction_patents', 2010, 2014, 2016, 2020)
    solar_multi   = compute_multiplier(df_energy, 'solar_patents',             2010, 2014, 2016, 2020)
    wind_multi    = compute_multiplier(df_energy, 'wind_patents',              2010, 2014, 2016, 2020)

    # 
    # TREND 3: Battery Storage Bonus — Oil Extraction vs Battery Innovation
    # Legacy:   E21B (oil and gas drilling)
    # Emerging: H01M (batteries — electrochemical energy storage)
    # Hypothesis: battery patents show one of the most aggressive
    # hockey stick curves in the entire USPTO database post-2015
    # proving the renewable grid cannot exist without storage innovation
    # 
    print("Running Trend 3: Bonus — Oil Extraction vs Battery Storage (E21B vs H01M)...")
    df_battery = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'E21B'
                THEN 1 ELSE 0 END)          AS oil_extraction_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'H01M'
                THEN 1 ELSE 0 END)          AS battery_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1995 AND 2022
          AND cd.cpc_subclass IN ('E21B', 'H01M')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    df_battery['oil_growth']     = df_battery['oil_extraction_patents'].pct_change().mul(100).round(2)
    df_battery['battery_growth'] = df_battery['battery_patents'].pct_change().mul(100).round(2)

    battery_inflect    = find_inflection(df_battery, 'battery_patents')
    crossover_battery  = find_crossover(df_battery, 'battery_patents', 'oil_extraction_patents')

    # Pre vs post Tesla Model S 2012 and Paris Agreement 2015
    oil_multi_2015     = compute_multiplier(df_battery, 'oil_extraction_patents', 2010, 2014, 2016, 2020)
    battery_multi_2015 = compute_multiplier(df_battery, 'battery_patents',        2010, 2014, 2016, 2020)

    conn.close()

    # ── CSV Exports ───────────────────────────────────────────────────────
    print("\nExporting CSVs...")
    df_media.to_csv(  f"{OUTPUT_DIR}/media_streaming_vs_optical.csv",   index=False)
    df_energy.to_csv( f"{OUTPUT_DIR}/energy_renewables_vs_fossil.csv",  index=False)
    df_battery.to_csv(f"{OUTPUT_DIR}/energy_battery_vs_oil.csv",        index=False)

    # ── JSON Export ───────────────────────────────────────────────────────
    print("Writing media and energy analysis JSON...")
    report = {
        "media_streaming_vs_optical"      : df_media.to_dict(orient="records"),
        "media_optical_peak_year"         : optical_peak,
        "media_streaming_inflection_year" : streaming_inflect,
        "media_crossover_year"            : crossover_media,
        "media_optical_multiplier_post_netflix"  : optical_pre,
        "media_streaming_multiplier_post_netflix": stream_multi,

        "energy_renewables_vs_fossil"     : df_energy.to_dict(orient="records"),
        "energy_fossil_peak_year"         : fossil_peak,
        "energy_solar_inflection_year"    : solar_inflect,
        "energy_crossover_year"           : crossover_energy,
        "energy_fossil_multiplier_post_paris"    : fossil_multi,
        "energy_solar_multiplier_post_paris"     : solar_multi,
        "energy_wind_multiplier_post_paris"      : wind_multi,

        "battery_vs_oil"                  : df_battery.to_dict(orient="records"),
        "battery_inflection_year"         : battery_inflect,
        "battery_crossover_year"          : crossover_battery,
        "battery_multiplier_post_paris"   : battery_multi_2015,
        "oil_multiplier_post_paris"       : oil_multi_2015,

        "policy_annotations": {
            "media"  : {
                "2007": "Netflix launches streaming",
                "2008": "Spotify launches",
                "2013": "Blu-ray peaks then collapses"
            },
            "energy" : {
                "1997": "Kyoto Protocol",
                "2010": "Solar costs begin collapsing",
                "2011": "Solar PV patents separate from fossil R&D",
                "2015": "Paris Agreement",
                "2022": "US Inflation Reduction Act"
            },
            "battery": {
                "2012": "Tesla Model S launch",
                "2015": "Tesla Powerwall announced",
                "2015": "Paris Agreement",
                "2020": "Global EV tipping point"
            }
        }
    }
    with open(f"{OUTPUT_DIR}/media_energy_report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    # ── Console Report ────────────────────────────────────────────────────
    print("\n======= MEDIA & ENERGY DISRUPTION DIAGNOSTICS =======")

    # Trend 1 — Physical Media
    print("\n  TREND 1: Death of Physical Media — Streaming vs Optical Discs")
    print(f"  Optical disc patents peaked:     {optical_peak}")
    print(f"  Streaming inflection year:       {streaming_inflect}")
    if crossover_media:
        print(f"  *** Crossover year: {crossover_media} — streaming overtook optical discs ***")
    else:
        print("  No crossover yet — streaming growth rate is the diagnostic")
    print(f"  Streaming multiplier post-Netflix 2007:  {stream_multi}x")
    print(f"  Optical multiplier post-Netflix 2007:    {optical_pre}x")
    print(f"\n  {'Year':<6} {'Optical G11B':>13} {'Streaming H04L':>15}  Event")
    print(f"  {'-'*6} {'-'*13} {'-'*15}  {'-'*30}")
    events_media = {
        2007: "Netflix streaming launch",
        2008: "Spotify launches",
        2010: "iPad launch kills physical media",
        2013: "Blu-ray peaks",
        2020: "COVID accelerates streaming"
    }
    milestones = [1995, 2000, 2005, 2007, 2008, 2010, 2013, 2015, 2018, 2020, 2022]
    for _, r in df_media[df_media['year'].isin(milestones)].iterrows():
        event = events_media.get(int(r['year']), "")
        print(f"  {int(r['year']):<6} {int(r['optical_disc_patents']):>13,} "
              f"{int(r['streaming_patents']):>15,}  {event}")

    # Trend 2 — Renewables vs Fossil
    print("\n  TREND 2: Renewables vs Fossil Fuel Extraction")
    print(f"  Fossil extraction peak year:    {fossil_peak}")
    print(f"  Solar PV inflection year:       {solar_inflect}")
    if crossover_energy:
        print(f"  *** Crossover year: {crossover_energy} — renewables overtook fossil extraction ***")
    else:
        print("  No crossover yet — solar growth rate vs fossil flatline is the story")
    print(f"  Fossil multiplier post-Paris 2015:    {fossil_multi}x")
    print(f"  Solar multiplier post-Paris 2015:     {solar_multi}x")
    print(f"  Wind multiplier post-Paris 2015:      {wind_multi}x")
    print(f"\n  {'Year':<6} {'Fossil E21B':>12} {'Solar H02S':>11} {'Wind F03D':>10} {'Renewable Total':>16}  Event")
    print(f"  {'-'*6} {'-'*12} {'-'*11} {'-'*10} {'-'*16}  {'-'*25}")
    events_energy = {
        1997: "Kyoto Protocol",
        2010: "Solar costs collapse",
        2011: "Solar PV separates",
        2015: "Paris Agreement",
        2022: "US IRA signed"
    }
    milestones = [1995, 2000, 2005, 2010, 2011, 2015, 2018, 2020, 2022]
    for _, r in df_energy[df_energy['year'].isin(milestones)].iterrows():
        event = events_energy.get(int(r['year']), "")
        print(f"  {int(r['year']):<6} {int(r['fossil_extraction_patents']):>12,} "
              f"{int(r['solar_patents']):>11,} "
              f"{int(r['wind_patents']):>10,} "
              f"{int(r['total_renewable_patents']):>16,}  {event}")

    # Trend 3 — Battery vs Oil
    print("\n  TREND 3: Battery Storage vs Oil Extraction (Hockey Stick)")
    print(f"  Battery patent inflection year:  {battery_inflect}")
    if crossover_battery:
        print(f"  *** Crossover year: {crossover_battery} — battery patents overtook oil extraction ***")
    else:
        print("  No crossover yet — battery growth trajectory is the diagnostic")
    print(f"  Oil extraction multiplier post-2015:     {oil_multi_2015}x")
    print(f"  Battery storage multiplier post-2015:    {battery_multi_2015}x")
    print(f"\n  {'Year':<6} {'Oil E21B':>10} {'Battery H01M':>13}  Event")
    print(f"  {'-'*6} {'-'*10} {'-'*13}  {'-'*30}")
    events_battery = {
        2012: "Tesla Model S launch",
        2015: "Tesla Powerwall + Paris Agreement",
        2020: "Global EV tipping point"
    }
    milestones = [1995, 2000, 2005, 2010, 2012, 2015, 2018, 2020, 2022]
    for _, r in df_battery[df_battery['year'].isin(milestones)].iterrows():
        event = events_battery.get(int(r['year']), "")
        print(f"  {int(r['year']):<6} {int(r['oil_extraction_patents']):>10,} "
              f"{int(r['battery_patents']):>13,}  {event}")

    print("\n======================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("======================================================\n")

if __name__ == "__main__":
    run_media_energy_analysis()