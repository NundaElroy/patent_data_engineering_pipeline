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

def find_inflection(df, col):
    """Return year of maximum year-over-year growth rate."""
    df = df.copy()
    df['growth'] = df[col].pct_change() * 100
    idx = df['growth'].idxmax()
    return int(df.loc[idx, 'year'])

def run_guard_analysis():
    print("Connecting to database...")
    conn = get_conn()

    # 
    # TREND 1: FinTech Shift — Digital Ledgers vs Traditional Banking
    # Legacy:   G06Q 40/02 (traditional banking, ATMs, loans)
    # Emerging: G06Q 20/06 (digital currency payment protocols)
    #           H04L 9/32  (secure communication, authentication)
    # Hypothesis: traditional banking patents remained flat for 20 years
    # while blockchain/digital finance exploded post-2015
    # 
    print("\nRunning Trend 1: FinTech Shift (Digital vs Traditional Banking)...")
    df_t1 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'G06Q'
                THEN 1 ELSE 0 END)                          AS traditional_banking_patents,
            SUM(CASE WHEN cd.cpc_subclass IN ('H04L')
                THEN 1 ELSE 0 END)                          AS digital_finance_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1995 AND 2022
          AND cd.cpc_subclass IN ('G06Q', 'H04L')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Also get more granular subclass level
    df_t1_detail = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'G06Q'
                THEN 1 ELSE 0 END)                          AS banking_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'H04L'
                THEN 1 ELSE 0 END)                          AS secure_comms_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1995 AND 2022
          AND cd.cpc_subclass IN ('G06Q', 'H04L')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Growth rates
    df_t1['banking_growth']  = df_t1['traditional_banking_patents'].pct_change().mul(100).round(2)
    df_t1['digital_growth']  = df_t1['digital_finance_patents'].pct_change().mul(100).round(2)

    # Pre vs post 2015 comparison
    pre_2015_banking  = df_t1[df_t1['year'].between(2010, 2014)]['traditional_banking_patents'].mean()
    post_2015_banking = df_t1[df_t1['year'].between(2016, 2020)]['traditional_banking_patents'].mean()
    pre_2015_digital  = df_t1[df_t1['year'].between(2010, 2014)]['digital_finance_patents'].mean()
    post_2015_digital = df_t1[df_t1['year'].between(2016, 2020)]['digital_finance_patents'].mean()

    banking_multiplier = round(post_2015_banking / pre_2015_banking, 2) if pre_2015_banking > 0 else None
    digital_multiplier = round(post_2015_digital / pre_2015_digital, 2) if pre_2015_digital > 0 else None

    crossover_t1   = find_crossover(df_t1, 'digital_finance_patents', 'traditional_banking_patents')
    inflection_t1  = find_inflection(df_t1, 'digital_finance_patents')

    # 
    # TREND 2: Genetic Revolution — Biological vs Chemical Medicine
    # Legacy:   A61K 31/00 → A61K (traditional drug preparations)
    # Emerging: C12N 15/00 → C12N (genetic engineering, recombinant DNA)
    # Hypothesis: while traditional pharma is high volume, genomics/biotech
    # growth rate post-2012 is significantly higher proving a fundamental
    # shift in how disease treatment is being innovated
    # 
    print("Running Trend 2: Genetic Revolution (Genomics vs Chemical Pharma)...")
    df_t2 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'A61K'
                THEN 1 ELSE 0 END)                          AS chemical_pharma_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'C12N'
                THEN 1 ELSE 0 END)                          AS genomics_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1990 AND 2022
          AND cd.cpc_subclass IN ('A61K', 'C12N')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Growth rates
    df_t2['pharma_growth']   = df_t2['chemical_pharma_patents'].pct_change().mul(100).round(2)
    df_t2['genomics_growth'] = df_t2['genomics_patents'].pct_change().mul(100).round(2)

    # Pre vs post CRISPR 2012
    pre_crispr_pharma    = df_t2[df_t2['year'].between(2005, 2011)]['chemical_pharma_patents'].mean()
    post_crispr_pharma   = df_t2[df_t2['year'].between(2013, 2019)]['chemical_pharma_patents'].mean()
    pre_crispr_genomics  = df_t2[df_t2['year'].between(2005, 2011)]['genomics_patents'].mean()
    post_crispr_genomics = df_t2[df_t2['year'].between(2013, 2019)]['genomics_patents'].mean()

    pharma_multiplier   = round(post_crispr_pharma   / pre_crispr_pharma,   2) if pre_crispr_pharma   > 0 else None
    genomics_multiplier = round(post_crispr_genomics / pre_crispr_genomics, 2) if pre_crispr_genomics > 0 else None

    crossover_t2  = find_crossover(df_t2, 'genomics_patents', 'chemical_pharma_patents')
    inflection_t2 = find_inflection(df_t2, 'genomics_patents')

    # Human Genome Project completed 2003, CRISPR discovered 2012
    # COVID mRNA vaccines 2020 — mark all three as annotation points

    # 
    # TREND 3: Retail Flip — E-Commerce Logistics vs Brick and Mortar
    # Legacy:   G06Q 30/00 (general commerce, physical shopping systems)
    # Emerging: G06Q 10/08 (logistics, inventory, delivery management)
    #           B64U        (unmanned aerial vehicles, drones)
    # Hypothesis: physical retail innovation stagnated as e-commerce
    # logistics and drone delivery patents exploded post-2012
    # Amazon effect visible as sharp inflection after 2012 Prime launch
    # 
    print("Running Trend 3: Retail Flip (E-Commerce vs Brick and Mortar)...")
    df_t3 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'G06Q'
                THEN 1 ELSE 0 END)                          AS commerce_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'B64U'
                THEN 1 ELSE 0 END)                          AS drone_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 2000 AND 2022
          AND cd.cpc_subclass IN ('G06Q', 'B64U')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Growth rates
    df_t3['commerce_growth'] = df_t3['commerce_patents'].pct_change().mul(100).round(2)
    df_t3['drone_growth']    = df_t3['drone_patents'].pct_change().mul(100).round(2)

    # Pre vs post Amazon Prime 2012
    pre_amazon_commerce  = df_t3[df_t3['year'].between(2008, 2011)]['commerce_patents'].mean()
    post_amazon_commerce = df_t3[df_t3['year'].between(2013, 2018)]['commerce_patents'].mean()
    pre_amazon_drone     = df_t3[df_t3['year'].between(2008, 2011)]['drone_patents'].mean()
    post_amazon_drone    = df_t3[df_t3['year'].between(2013, 2018)]['drone_patents'].mean()

    commerce_multiplier = round(post_amazon_commerce / pre_amazon_commerce, 2) if pre_amazon_commerce > 0 else None
    drone_multiplier    = round(post_amazon_drone    / pre_amazon_drone,    2) if pre_amazon_drone    > 0 else None

    inflection_t3 = find_inflection(df_t3, 'drone_patents')

    conn.close()

    # ── CSV Exports ───────────────────────────────────────────────────────
    print("\nExporting CSVs...")
    df_t1.to_csv(        f"{OUTPUT_DIR}/guard_fintech_vs_banking.csv",      index=False)
    df_t1_detail.to_csv( f"{OUTPUT_DIR}/guard_fintech_detail.csv",          index=False)
    df_t2.to_csv(        f"{OUTPUT_DIR}/guard_genomics_vs_pharma.csv",      index=False)
    df_t3.to_csv(        f"{OUTPUT_DIR}/guard_ecommerce_vs_retail.csv",     index=False)

    # ── JSON Export ───────────────────────────────────────────────────────
    print("Writing changing of the guard JSON...")
    report = {
        "fintech_vs_banking"              : df_t1.to_dict(orient="records"),
        "fintech_crossover_year"          : crossover_t1,
        "fintech_inflection_year"         : inflection_t1,
        "banking_multiplier_post_2015"    : banking_multiplier,
        "digital_multiplier_post_2015"    : digital_multiplier,
        "genomics_vs_pharma"              : df_t2.to_dict(orient="records"),
        "genomics_crossover_year"         : crossover_t2,
        "genomics_inflection_year"        : inflection_t2,
        "pharma_multiplier_post_crispr"   : pharma_multiplier,
        "genomics_multiplier_post_crispr" : genomics_multiplier,
        "ecommerce_vs_retail"             : df_t3.to_dict(orient="records"),
        "drone_inflection_year"           : inflection_t3,
        "commerce_multiplier_post_amazon" : commerce_multiplier,
        "drone_multiplier_post_amazon"    : drone_multiplier,
        "policy_annotations": {
            "fintech"  : {"2009": "Bitcoin whitepaper", "2015": "Blockchain mainstream", "2020": "DeFi explosion"},
            "genomics" : {"2003": "Human Genome Project", "2012": "CRISPR discovered", "2020": "mRNA COVID vaccine"},
            "ecommerce": {"2012": "Amazon Prime launch", "2013": "Amazon drone announcement", "2020": "COVID accelerates e-commerce"},
        }
    }
    with open(f"{OUTPUT_DIR}/guard_report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    # ── Console Report ────────────────────────────────────────────────────
    print("\n======= CHANGING OF THE GUARD — DIAGNOSTIC REPORT =======")

    # Trend 1
    print("\n  TREND 1: FinTech Shift — Digital Finance vs Traditional Banking")
    print(f"  Traditional banking avg patents 2010-2014:  {int(pre_2015_banking):,}")
    print(f"  Traditional banking avg patents 2016-2020:  {int(post_2015_banking):,}  ({banking_multiplier}x)")
    print(f"  Digital finance avg patents 2010-2014:      {int(pre_2015_digital):,}")
    print(f"  Digital finance avg patents 2016-2020:      {int(post_2015_digital):,}  ({digital_multiplier}x)")
    if crossover_t1:
        print(f"  *** Crossover year: {crossover_t1} — digital finance overtook traditional banking ***")
    else:
        print(f"  No crossover yet — check growth rates below")
    print(f"  Peak digital finance growth year: {inflection_t1}")
    print(f"\n  {'Year':<6} {'Traditional':>12} {'Digital':>10}  Event")
    print(f"  {'-'*6} {'-'*12} {'-'*10}  {'-'*30}")
    events_t1 = {2009: "Bitcoin whitepaper", 2015: "Blockchain mainstream", 2020: "DeFi explosion"}
    milestones = [1995, 2000, 2005, 2009, 2012, 2015, 2018, 2020, 2022]
    for _, r in df_t1[df_t1['year'].isin(milestones)].iterrows():
        event = events_t1.get(int(r['year']), "")
        print(f"  {int(r['year']):<6} {int(r['traditional_banking_patents']):>12,} "
              f"{int(r['digital_finance_patents']):>10,}  {event}")

    # Trend 2
    print("\n  TREND 2: Genetic Revolution — Genomics vs Chemical Pharma")
    print(f"  Chemical pharma avg patents 2005-2011:  {int(pre_crispr_pharma):,}")
    print(f"  Chemical pharma avg patents 2013-2019:  {int(post_crispr_pharma):,}  ({pharma_multiplier}x)")
    print(f"  Genomics avg patents 2005-2011:         {int(pre_crispr_genomics):,}")
    print(f"  Genomics avg patents 2013-2019:         {int(post_crispr_genomics):,}  ({genomics_multiplier}x)")
    if crossover_t2:
        print(f"  *** Crossover year: {crossover_t2} — genomics overtook chemical pharma ***")
    else:
        print(f"  No crossover yet — genomics growth rate is the key diagnostic")
    print(f"  Peak genomics growth year: {inflection_t2}")
    print(f"\n  {'Year':<6} {'Chem Pharma':>12} {'Genomics':>10}  Event")
    print(f"  {'-'*6} {'-'*12} {'-'*10}  {'-'*30}")
    events_t2 = {2003: "Human Genome Project", 2012: "CRISPR discovered", 2020: "mRNA COVID vaccine"}
    milestones = [1990, 1995, 2000, 2003, 2005, 2010, 2012, 2015, 2018, 2020, 2022]
    for _, r in df_t2[df_t2['year'].isin(milestones)].iterrows():
        event = events_t2.get(int(r['year']), "")
        print(f"  {int(r['year']):<6} {int(r['chemical_pharma_patents']):>12,} "
              f"{int(r['genomics_patents']):>10,}  {event}")

    # Trend 3
    print("\n  TREND 3: Retail Flip — E-Commerce Logistics vs Physical Retail")
    print(f"  Commerce avg patents 2008-2011:  {int(pre_amazon_commerce):,}")
    print(f"  Commerce avg patents 2013-2018:  {int(post_amazon_commerce):,}  ({commerce_multiplier}x)")
    print(f"  Drone avg patents 2008-2011:     {int(pre_amazon_drone):,}")
    print(f"  Drone avg patents 2013-2018:     {int(post_amazon_drone):,}  ({drone_multiplier}x)")
    print(f"  Peak drone innovation year: {inflection_t3}")
    print(f"\n  {'Year':<6} {'Commerce':>10} {'Drones':>8}  Event")
    print(f"  {'-'*6} {'-'*10} {'-'*8}  {'-'*35}")
    events_t3 = {2012: "Amazon Prime launch", 2013: "Amazon drone announcement", 2020: "COVID accelerates e-commerce"}
    milestones = [2000, 2005, 2010, 2012, 2013, 2015, 2018, 2020, 2022]
    for _, r in df_t3[df_t3['year'].isin(milestones)].iterrows():
        event = events_t3.get(int(r['year']), "")
        print(f"  {int(r['year']):<6} {int(r['commerce_patents']):>10,} "
              f"{int(r['drone_patents']):>8,}  {event}")

    print("\n==========================================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("==========================================================\n")

if __name__ == "__main__":
    run_guard_analysis()