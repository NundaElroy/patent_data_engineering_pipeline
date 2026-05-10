"""
Patent Intelligence Predictive Analytics (v2.0)
-----------------------------------------------
This module performs trend analysis and forecasting on USPTO patent data.
It specifically addresses the 'Quality vs. Quantity' problem by weighting 
patents by citation impact and using non-linear growth models for high-velocity 
technology sectors like Artificial Intelligence and Renewables.

Methodological Features:
1. Citation Weighting: Patents are weighted by (1 + citations) to favor 
   foundational innovations over volume-heavy 'filler' patents.
2. Reporting Lag Clamp: Data from 2020-2022 is excluded from training to 
   prevent the 18-month USPTO publication delay from skewing trends.
3. Log-Linear Modeling: Tech sectors are modeled using exponential growth 
   to capture the 'S-curve' of emerging innovation.
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
import json
import os
import math
from typing import Any, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")

# --- Configuration & Global Constraints ---
DB_PATH    = "patents.db"
OUTPUT_DIR = "./reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Sector-specific windows to capture the right 'regime' of innovation.
# Fossil fuels use a long-term window; Tech uses the modern post-2010 era.
FOSSIL_TRAIN_START = 1995
TECH_TRAIN_START   = 2010  
TRAIN_END          = 2019  
FORECAST_TO        = 2035

def get_conn():
    """Establishes a connection to the local SQLite patent database."""
    return sqlite3.connect(DB_PATH)

def run_query(conn, sql: str) -> pd.DataFrame:
    """Executes SQL queries and returns results as a Pandas DataFrame."""
    return pd.read_sql_query(sql, conn)

# --- Forecasting Core Logic ---

def fit_trend(df: pd.DataFrame, year_col: str, val_col: str, 
              train_start: int, train_end: int, model_type='linear') -> Tuple[float, float, float]:
    r"""
    Fits a statistical model to historical patent data.
    
    For 'linear' models: Fits $y = mx + b$. Best for mature industries (Fossil).
    For 'exponential' models: Fits $\ln(y) = mx + b$. Best for high-growth tech (AI).
    
    Returns:
        slope (m), intercept (b), and R-squared (goodness of fit).
    """
    # Filter for the training window and remove empty data points
    train = df[df[year_col].between(train_start, train_end)].dropna(subset=[val_col])
    x = train[year_col].values
    y = train[val_col].values

    if len(x) < 3: return 0.0, 0.0, 0.0

    # Transformation step for exponential growth
    if model_type == 'exponential':
        # log(y + 1) handles zero-value years gracefully
        y_fit = np.log(y + 1) 
    else:
        y_fit = y

    # Perform first-degree polynomial fit (Linear Regression)
    coeffs = np.polyfit(x, y_fit, 1)
    slope, intercept = float(coeffs[0]), float(coeffs[1])

    # Calculate R-squared in the original scale to ensure real-world accuracy
    if model_type == 'exponential':
        y_pred = np.exp(slope * x + intercept) - 1
    else:
        y_pred = slope * x + intercept
        
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return slope, intercept, round(r_squared, 4)

def project_trend(slope: float, intercept: float, from_year: int, to_year: int, model_type='linear'):
    """
    Extends the fitted model into the future.
    
    Clamps values to zero to prevent 'negative patents' in declining sectors.
    """
    years = list(range(from_year, to_year + 1))
    if model_type == 'exponential':
        # Re-convert from log space back to patent counts
        projected = [max(0, int(np.exp(slope * yr + intercept) - 1)) for yr in years]
    else:
        projected = [max(0, int(slope * yr + intercept)) for yr in years]
    return pd.DataFrame({"year": years, "projected_patents": projected})

def get_crossover_range(df_a: pd.DataFrame, df_b: pd.DataFrame, r2_a: float, r2_b: float) -> Tuple[Optional[int], Optional[str]]:
    """
    Identifies the year when Technology A overtakes Technology B.
    
    Calculates a confidence range based on the R-squared values.
    High R-squared (near 1.0) creates a narrow range; low R-squared creates 
    a wider uncertainty window.
    """
    merged = pd.merge(df_a, df_b, on="year", suffixes=('_a', '_b'))
    cross = merged[merged["projected_patents_a"] > merged["projected_patents_b"]]
    
    if cross.empty: 
        return None, None
    
    main_year = int(cross.iloc[0]["year"])
    
    # Statistical uncertainty logic: Lower fit quality equals more 'noise' in the date.
    avg_r2 = (r2_a + r2_b) / 2
    uncertainty_years = int((1 - avg_r2) * 10) 
    
    return main_year, f"{main_year - uncertainty_years} to {main_year + uncertainty_years}"

# --- Execution Logic ---

def run_predictive_analysis():
    """
    Main execution loop.
    1. Queries the DB for impact-weighted patent data.
    2. Trains sector-specific models (Exponential for Tech, Linear for Fossil).
    3. Projects future influence crossover events.
    """
    conn = get_conn()
    
    # --- P1: The AI Race ---
    # Weighting: 1 + num_citations ensures influential patents count for more.
    # FIX: Route the join through the relationships table to link patents to inventors
    ai_sql = """
        SELECT p.year,
               SUM(CASE WHEN i.country = 'US' THEN (1 + COALESCE(pc.citation_count, 0)) ELSE 0 END) AS us_ai_impact,
               SUM(CASE WHEN i.country = 'CN' THEN (1 + COALESCE(pc.citation_count, 0)) ELSE 0 END) AS cn_ai_impact
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        JOIN relationships r ON p.patent_id = r.patent_id
        JOIN inventors i ON r.inventor_id = i.inventor_id
        LEFT JOIN patent_citations pc ON p.patent_id = pc.patent_id
        WHERE cd.cpc_subclass = 'G06N' AND p.year BETWEEN 1995 AND 2022
        GROUP BY p.year
    """
    df_ai = run_query(conn, ai_sql)

    # Use Exponential models for the rapid AI expansion era (2010+)
    us_m, us_b, us_r2 = fit_trend(df_ai, 'year', 'us_ai_impact', TECH_TRAIN_START, TRAIN_END, 'exponential')
    cn_m, cn_b, cn_r2 = fit_trend(df_ai, 'year', 'cn_ai_impact', TECH_TRAIN_START, TRAIN_END, 'exponential')

    df_us_proj = project_trend(us_m, us_b, TRAIN_END + 1, FORECAST_TO, 'exponential')
    df_cn_proj = project_trend(cn_m, cn_b, TRAIN_END + 1, FORECAST_TO, 'exponential')
    ai_year, ai_range = get_crossover_range(df_cn_proj, df_us_proj, cn_r2, us_r2)

    # --- P2: Energy Future ---
    energy_sql = """
        SELECT p.year,
               SUM(CASE WHEN cd.cpc_subclass = 'E21B' THEN (1 + COALESCE(pc.citation_count, 0)) ELSE 0 END) AS fossil_impact,
               SUM(CASE WHEN cd.cpc_subclass IN ('H02S', 'F03D') THEN (1 + COALESCE(pc.citation_count, 0)) ELSE 0 END) AS renew_impact
        FROM patents p
        JOIN cpc_detail cd ON p.patent_id = cd.patent_id
        LEFT JOIN patent_citations pc ON p.patent_id = pc.patent_id
        WHERE p.year BETWEEN 1995 AND 2022
        GROUP BY p.year
    """
    df_energy = run_query(conn, energy_sql)

    # Fossil is a mature mechanical field (Linear); Renewables are high-tech electronics (Exponential)
    fos_m, fos_b, fos_r2 = fit_trend(df_energy, 'year', 'fossil_impact', FOSSIL_TRAIN_START, TRAIN_END, 'linear')
    ren_m, ren_b, ren_r2 = fit_trend(df_energy, 'year', 'renew_impact', TECH_TRAIN_START, TRAIN_END, 'exponential')

    df_fos_proj = project_trend(fos_m, fos_b, TRAIN_END + 1, FORECAST_TO, 'linear')
    df_ren_proj = project_trend(ren_m, ren_b, TRAIN_END + 1, FORECAST_TO, 'exponential')
    en_year, en_range = get_crossover_range(df_ren_proj, df_fos_proj, ren_r2, fos_r2)

    conn.close()

    # --- Results Presentation ---
    print("\n============= REFINED PREDICTIVE REPORT =============")
    print("LOGIC: Data from 2020-2022 is excluded from training to bypass reporting lag.")
    
    print(f"\n[P1: AI RACE - IMPACT WEIGHTED]")
    print(f"US R²: {us_r2} | CN R²: {cn_r2}")
    if ai_year:
        print(f"PREDICTION: China overtakes US impact by {ai_year} (Range: {ai_range})")
    else:
        print(f"PREDICTION: US maintains lead through {FORECAST_TO}")

    print(f"\n[P2: ENERGY FUTURE - IMPACT WEIGHTED]")
    print(f"Fossil R²: {fos_r2} | Renewables R²: {ren_r2}")
    if en_year:
        print(f"PREDICTION: Renewables overtake Fossil by {en_year} (Range: {en_range})")
    else:
        print(f"PREDICTION: Fossil remains dominant through {FORECAST_TO}")

    # --- CSV Export Logic ---
    print(f"\n[!] Exporting projection data to CSV...")
    
    # Merge and export the AI projections
    df_ai_proj_merged = pd.merge(df_us_proj, df_cn_proj, on="year", suffixes=('_us', '_cn'))
    ai_csv_path = os.path.join(OUTPUT_DIR, "ai_race_projections.csv")
    df_ai_proj_merged.to_csv(ai_csv_path, index=False)
    print(f" -> Saved: {ai_csv_path}")
    
    # Merge and export the Energy projections
    df_en_proj_merged = pd.merge(df_fos_proj, df_ren_proj, on="year", suffixes=('_fossil', '_renewable'))
    en_csv_path = os.path.join(OUTPUT_DIR, "energy_future_projections.csv")
    df_en_proj_merged.to_csv(en_csv_path, index=False)
    print(f" -> Saved: {en_csv_path}")

if __name__ == "__main__":
    run_predictive_analysis()