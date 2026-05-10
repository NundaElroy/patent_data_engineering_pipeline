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

def compute_peak_year(df, col):
    """Return year where col is maximum."""
    idx = df[col].idxmax()
    return int(df.loc[idx, 'year'])

def compute_lag(peak_a, peak_b):
    """Return how many years b lags behind a."""
    return peak_b - peak_a

def linear_forecast(df, year_col, val_col, forecast_years=5):
    """Simple linear regression forecast."""
    from numpy.polynomial import polynomial as P
    import numpy as np
    x = df[year_col].values
    y = df[val_col].values
    coeffs = np.polyfit(x, y, 1)
    last_year = int(x[-1])
    future_years = list(range(last_year + 1, last_year + forecast_years + 1))
    forecast = [max(0, int(coeffs[0] * yr + coeffs[1])) for yr in future_years]
    return future_years, forecast, round(float(coeffs[0]), 2)

def run_trend_analysis():
    print("Connecting to database...")
    conn = get_conn()

    #
    # T1: H01L Enabling G06F — Chips Before Software
    # Hypothesis: semiconductor patents (H01L) peaked before computing
    # patents (G06F) — proving chips are the infrastructure that
    # software innovation builds on with a measurable time lag
    #
    print("\nRunning T1: H01L Enabling G06F (Chips before Software)...")
    df_t1 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'H01L' THEN 1 ELSE 0 END) AS semiconductor_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'G06F' THEN 1 ELSE 0 END) AS computing_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1976 AND 2022
          AND cd.cpc_subclass IN ('H01L', 'G06F')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Compute growth rates
    df_t1['semi_growth'] = df_t1['semiconductor_patents'].pct_change().round(4) * 100
    df_t1['comp_growth'] = df_t1['computing_patents'].pct_change().round(4) * 100

    #
    # T2: H04L Before H04W — Infrastructure Before Mobile
    # Hypothesis: data transmission patents (H04L) peaked before
    # wireless patents (H04W) by 3-5 years — proving network
    # infrastructure investment always precedes mobile application growth
    #
    print("Running T2: H04L Before H04W (Infrastructure before Mobile)...")
    df_t2 = run_query(conn, """
        SELECT
            p.year,
            SUM(CASE WHEN cd.cpc_subclass = 'H04L' THEN 1 ELSE 0 END) AS transmission_patents,
            SUM(CASE WHEN cd.cpc_subclass = 'H04W' THEN 1 ELSE 0 END) AS wireless_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE p.year BETWEEN 1990 AND 2022
          AND cd.cpc_subclass IN ('H04L', 'H04W')
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    #
    # T3: Patent Volume Predicting Commercial Products (3G/4G/5G lag)
    # Hypothesis: wireless patent peaks consistently precede commercial
    # product rollouts by 4-5 years — proving patents are a leading
    # geopolitical and commercial indicator
    # Known milestones:
    #   3G patents peaked ~2004 → 3G mainstream 2008-2009
    #   4G patents peaked ~2012 → 4G mainstream 2016
    #   5G patents peaked ~2018 → 5G mainstream 2022
    #
    print("Running T3: Patent Volume Predicting Commercial Products (3G/4G/5G)...")
    df_t3 = run_query(conn, """
        SELECT
            p.year,
            COUNT(DISTINCT p.patent_id) AS wireless_patents
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        WHERE cd.cpc_subclass = 'H04W'
          AND p.year BETWEEN 1995 AND 2022
        GROUP BY p.year
        ORDER BY p.year ASC;
    """)

    # Rolling 3yr average to smooth noise
    df_t3['rolling_3yr'] = df_t3['wireless_patents'].rolling(3, min_periods=1).mean().round(0)

    # Forecast next 5 years
    df_t3_clean = df_t3[df_t3['year'] <= 2019].copy()  # use pre-cutoff for forecast
    future_years, forecast_vals, slope = linear_forecast(df_t3_clean, 'year', 'wireless_patents')

    conn.close()

    # ── Peak year analysis ────────────────────────────────────────────────
    t1_semi_peak = compute_peak_year(df_t1, 'semiconductor_patents')
    t1_comp_peak = compute_peak_year(df_t1, 'computing_patents')
    t1_lag       = compute_lag(t1_semi_peak, t1_comp_peak)

    t2_trans_peak   = compute_peak_year(df_t2, 'transmission_patents')
    t2_wireless_peak = compute_peak_year(df_t2, 'wireless_patents')
    t2_lag           = compute_lag(t2_trans_peak, t2_wireless_peak)

    # ── CSV Exports ───────────────────────────────────────────────────────
    print("\nExporting CSVs...")
    df_t1.to_csv(f"{OUTPUT_DIR}/trend_chips_before_software.csv",    index=False)
    df_t2.to_csv(f"{OUTPUT_DIR}/trend_infra_before_mobile.csv",      index=False)
    df_t3.to_csv(f"{OUTPUT_DIR}/trend_wireless_forecast.csv",        index=False)

    # Forecast CSV
    df_forecast = pd.DataFrame({
        "year"              : future_years,
        "forecast_patents"  : forecast_vals,
        "type"              : "forecast"
    })
    df_forecast.to_csv(f"{OUTPUT_DIR}/trend_wireless_forecast_5yr.csv", index=False)

    # ── JSON Export ───────────────────────────────────────────────────────
    print("Writing trend diagnostics JSON...")
    report = {
        "trend_chips_before_software" : df_t1.to_dict(orient="records"),
        "trend_infra_before_mobile"   : df_t2.to_dict(orient="records"),
        "trend_wireless_history"      : df_t3.to_dict(orient="records"),
        "trend_wireless_forecast"     : df_forecast.to_dict(orient="records"),
        "trend_lag_analysis": {
            "h01l_peak_year"         : t1_semi_peak,
            "g06f_peak_year"         : t1_comp_peak,
            "chips_to_software_lag"  : t1_lag,
            "h04l_peak_year"         : t2_trans_peak,
            "h04w_peak_year"         : t2_wireless_peak,
            "infra_to_mobile_lag"    : t2_lag,
            "forecast_slope"         : slope,
        }
    }
    with open(f"{OUTPUT_DIR}/trend_report.json", "w", encoding="utf-8") as f:
        json.dump(_to_json_safe(report), f, indent=4, ensure_ascii=False, allow_nan=False)

    # ── Console Report ────────────────────────────────────────────────────
    print("\n======== SECTION 4: TREND DIAGNOSTICS ========")

    # T1
    print("\n  T1: H01L Enabling G06F — Chips Before Software")
    print(f"  H01L semiconductor patents peaked: {t1_semi_peak}")
    print(f"  G06F computing patents peaked:     {t1_comp_peak}")
    print(f"  Lag: {t1_lag} years — {'chips led software as expected' if t1_lag > 0 else 'unexpected — software led chips'}")
    print(f"\n  {'Year':<6} {'Semiconductors':>15} {'Computing':>12} {'Semi Growth%':>13} {'Comp Growth%':>13}")
    print(f"  {'-'*6} {'-'*15} {'-'*12} {'-'*13} {'-'*13}")
    milestones = [1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2019, 2022]
    for _, r in df_t1[df_t1['year'].isin(milestones)].iterrows():
        sg = f"{float(r['semi_growth']):>12.1f}%" if pd.notna(r['semi_growth']) else "          N/A"
        cg = f"{float(r['comp_growth']):>12.1f}%" if pd.notna(r['comp_growth']) else "          N/A"
        print(f"  {int(r['year']):<6} {int(r['semiconductor_patents']):>15,} "
              f"{int(r['computing_patents']):>12,} {sg} {cg}")

    # T2
    print("\n  T2: H04L Before H04W — Infrastructure Before Mobile")
    print(f"  H04L transmission patents peaked: {t2_trans_peak}")
    print(f"  H04W wireless patents peaked:     {t2_wireless_peak}")
    print(f"  Lag: {t2_lag} years — {'infrastructure led mobile as expected' if t2_lag > 0 else 'unexpected result'}")
    print(f"\n  {'Year':<6} {'Transmission H04L':>18} {'Wireless H04W':>14}")
    print(f"  {'-'*6} {'-'*18} {'-'*14}")
    milestones = [1990, 1995, 2000, 2003, 2005, 2007, 2010, 2014, 2018, 2022]
    for _, r in df_t2[df_t2['year'].isin(milestones)].iterrows():
        marker = " <- 4G rollout" if int(r['year']) == 2010 else ""
        marker = " <- iPhone"     if int(r['year']) == 2007 else marker
        print(f"  {int(r['year']):<6} {int(r['transmission_patents']):>18,} "
              f"{int(r['wireless_patents']):>14,}{marker}")

    # T3
    print("\n  T3: Patent Volume Predicting Commercial Products (3G/4G/5G)")
    print("  Known lag: patents peak ~4-5 years before commercial rollout")
    print(f"  Forecast slope: {slope:+.0f} patents/year")
    print(f"\n  Historical:")
    print(f"  {'Year':<6} {'H04W Patents':>13} {'3yr Avg':>10}  Event")
    print(f"  {'-'*6} {'-'*13} {'-'*10}  {'-'*30}")
    events = {
        2000: "3G standardization",
        2004: "3G patents peak (predicted)",
        2007: "iPhone launch",
        2009: "3G mainstream",
        2012: "4G patents peak (predicted)",
        2016: "4G mainstream",
        2018: "5G patents peak (predicted)",
        2022: "5G mainstream",
    }
    for _, r in df_t3.iterrows():
        yr = int(r['year'])
        event = events.get(yr, "")
        print(f"  {yr:<6} {int(r['wireless_patents']):>13,} "
              f"{int(r['rolling_3yr']):>10,}  {event}")

    print(f"\n  5-Year Forecast (linear projection):")
    print(f"  {'Year':<6} {'Forecast Patents':>16}")
    print(f"  {'-'*6} {'-'*16}")
    for yr, val in zip(future_years, forecast_vals):
        print(f"  {yr:<6} {val:>16,}")

    print("\n===============================================")
    print(f"  Reports saved to {OUTPUT_DIR}/")
    print("===============================================\n")

if __name__ == "__main__":
    run_trend_analysis()