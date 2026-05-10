from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from flask import Flask, render_template, request


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT_DIR / "reports" / "report.json"
WEIGHTED_REPORT_PATH = ROOT_DIR / "reports" / "weighted_report.json"
DISPLACEMENT_REPORT_PATH = ROOT_DIR / "reports" / "displacement_report.json"
GEOPOLITICAL_REPORT_PATH = ROOT_DIR / "reports" / "geopolitical_report.json"
IBM_VS_SAMSUNG_PATH = ROOT_DIR / "reports" / "company_ibm_vs_samsung.csv"
MEDIA_STREAMING_VS_OPTICAL_PATH = ROOT_DIR / "reports" / "media_streaming_vs_optical.csv"
ENERGY_RENEWABLES_VS_FOSSIL_PATH = ROOT_DIR / "reports" / "energy_renewables_vs_fossil.csv"
ENERGY_BATTERY_VS_OIL_PATH = ROOT_DIR / "reports" / "energy_battery_vs_oil.csv"
CPC_REPORT_PATH = ROOT_DIR / "reports" / "cpc_report.json"
CPC_TOP_COMPANIES_PATH = ROOT_DIR / "reports" / "cpc_top_companies.csv"

MIN_DASHBOARD_YEAR = 1900

COLORWAY = [
    "#3B82F6",
    "#F97316",
    "#10B981",
    "#A855F7",
    "#06B6D4",
    "#EF4444",
    "#F59E0B",
    "#EC4899",
    "#84CC16",
]


# CPC/IPC section meanings (high-level categories)
CPC_SECTION_LABELS: dict[str, str] = {
    "A": "Human necessities",
    "B": "Performing operations; transporting",
    "C": "Chemistry; metallurgy",
    "D": "Textiles; paper",
    "E": "Fixed constructions",
    "F": "Mechanical engineering; lighting; heating; weapons; blasting",
    "G": "Physics",
    "H": "Electricity",
    "Y": "General tagging of new technological developments (cross-sectional)",
}


@dataclass(frozen=True)
class DashboardFilters:
    start_year: int
    end_year: int


def _parse_int(value: str | None, *, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def load_report() -> dict[str, Any]:
    if not REPORT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {REPORT_PATH}. Run analysis.py (or sanitize existing report.json) first."
        )

    with REPORT_PATH.open("r", encoding="utf-8") as f:
        # Python's json can parse NaN; we later normalize for charting.
        return json.load(f)


def report_last_updated() -> str:
    ts = datetime.fromtimestamp(REPORT_PATH.stat().st_mtime)
    return ts.strftime("%Y-%m-%d %H:%M")


@lru_cache(maxsize=1)
def load_cpc_report() -> dict[str, Any]:
    if not CPC_REPORT_PATH.exists():
        return {}

    with CPC_REPORT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_weighted_report() -> dict[str, Any]:
    if not WEIGHTED_REPORT_PATH.exists():
        return {}

    with WEIGHTED_REPORT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_displacement_report() -> dict[str, Any]:
    if not DISPLACEMENT_REPORT_PATH.exists():
        return {}

    with DISPLACEMENT_REPORT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_geopolitical_report() -> dict[str, Any]:
    if not GEOPOLITICAL_REPORT_PATH.exists():
        return {}

    with GEOPOLITICAL_REPORT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_ibm_vs_samsung() -> list[dict[str, Any]]:
    if not IBM_VS_SAMSUNG_PATH.exists():
        return []
    df = pd.read_csv(IBM_VS_SAMSUNG_PATH)
    if df.empty:
        return []
    df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
    df["ibm_patents"] = pd.to_numeric(df.get("ibm_patents"), errors="coerce")
    df["samsung_patents"] = pd.to_numeric(df.get("samsung_patents"), errors="coerce")
    df = df.dropna(subset=["year", "ibm_patents", "samsung_patents"]).copy()
    df["year"] = df["year"].astype(int)
    return df.to_dict(orient="records")


@lru_cache(maxsize=1)
def load_media_streaming_vs_optical() -> list[dict[str, Any]]:
    if not MEDIA_STREAMING_VS_OPTICAL_PATH.exists():
        return []
    df = pd.read_csv(MEDIA_STREAMING_VS_OPTICAL_PATH)
    if df.empty:
        return []
    df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
    df["optical_disc_patents"] = pd.to_numeric(df.get("optical_disc_patents"), errors="coerce")
    df["streaming_patents"] = pd.to_numeric(df.get("streaming_patents"), errors="coerce")
    df = df.dropna(subset=["year", "optical_disc_patents", "streaming_patents"]).copy()
    df["year"] = df["year"].astype(int)
    return df.to_dict(orient="records")


@lru_cache(maxsize=1)
def load_energy_renewables_vs_fossil() -> list[dict[str, Any]]:
    if not ENERGY_RENEWABLES_VS_FOSSIL_PATH.exists():
        return []
    df = pd.read_csv(ENERGY_RENEWABLES_VS_FOSSIL_PATH)
    if df.empty:
        return []
    df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
    df["fossil_extraction_patents"] = pd.to_numeric(df.get("fossil_extraction_patents"), errors="coerce")
    df["total_renewable_patents"] = pd.to_numeric(df.get("total_renewable_patents"), errors="coerce")
    df = df.dropna(subset=["year", "fossil_extraction_patents", "total_renewable_patents"]).copy()
    df["year"] = df["year"].astype(int)
    return df.to_dict(orient="records")


@lru_cache(maxsize=1)
def load_energy_battery_vs_oil() -> list[dict[str, Any]]:
    if not ENERGY_BATTERY_VS_OIL_PATH.exists():
        return []
    df = pd.read_csv(ENERGY_BATTERY_VS_OIL_PATH)
    if df.empty:
        return []
    df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
    df["oil_extraction_patents"] = pd.to_numeric(df.get("oil_extraction_patents"), errors="coerce")
    df["battery_patents"] = pd.to_numeric(df.get("battery_patents"), errors="coerce")
    df = df.dropna(subset=["year", "oil_extraction_patents", "battery_patents"]).copy()
    df["year"] = df["year"].astype(int)
    return df.to_dict(orient="records")


def cpc_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Prefer CPC data embedded in the main report.json; fallback to cpc_report.json."""
    if report.get("cpc_sections") or report.get("cpc_growth_by_decade"):
        return {
            "cpc_sections": report.get("cpc_sections", []),
            "cpc_growth_by_decade": report.get("cpc_growth_by_decade", []),
        }
    return load_cpc_report()


@lru_cache(maxsize=1)
def load_cpc_top_companies() -> list[dict[str, Any]]:
    if not CPC_TOP_COMPANIES_PATH.exists():
        return []
    df = pd.read_csv(CPC_TOP_COMPANIES_PATH)
    if df.empty:
        return []
    df["patents"] = pd.to_numeric(df.get("patents"), errors="coerce")
    df = df.dropna(subset=["cpc_section", "company_name", "patents"]).copy()
    df["cpc_section_label"] = df["cpc_section"].map(_cpc_label)
    df["patents"] = df["patents"].astype(int)
    return df.to_dict(orient="records")


def trends_df(report: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(report.get("yearly_trends", []))
    if df.empty:
        return df

    # Normalize types and ordering.
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["patents"] = pd.to_numeric(df["patents"], errors="coerce")
    df["rolling_5yr_avg"] = pd.to_numeric(df.get("rolling_5yr_avg"), errors="coerce")
    df["growth_pct"] = pd.to_numeric(df.get("growth_pct"), errors="coerce")

    df = df.dropna(subset=["year", "patents"]).copy()
    df["year"] = df["year"].astype(int)
    df = df.sort_values("year")
    return df


def apply_filters(df: pd.DataFrame, filters: DashboardFilters) -> pd.DataFrame:
    if df.empty:
        return df
    return df[(df["year"] >= filters.start_year) & (df["year"] <= filters.end_year)].copy()


def kpis(report: dict[str, Any], filtered_trends: pd.DataFrame) -> dict[str, Any]:
    total_patents = report.get("total_patents")
    peak = report.get("peak_year", {})

    latest_year = None
    latest_patents = None
    latest_rolling = None

    if not filtered_trends.empty:
        last_row = filtered_trends.iloc[-1]
        latest_year = int(last_row["year"])
        latest_patents = int(last_row["patents"]) if pd.notna(last_row["patents"]) else None
        rolling_val = last_row.get("rolling_5yr_avg")
        latest_rolling = int(rolling_val) if rolling_val is not None and pd.notna(rolling_val) else None

    return {
        "total_patents": int(total_patents) if total_patents is not None else None,
        "peak_year": peak.get("year"),
        "peak_year_patents": peak.get("patents"),
        "latest_year": latest_year,
        "latest_year_patents": latest_patents,
        "latest_rolling_5yr_avg": latest_rolling,
    }


def _bar_chart(
    items: list[dict[str, Any]],
    x_key: str,
    y_key: str,
    *,
    title: str,
    value_label: str = "patents",
) -> str:
    df = pd.DataFrame(items)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig.to_html(include_plotlyjs=False, full_html=False)

    df[y_key] = pd.to_numeric(df[y_key], errors="coerce")
    df = df.dropna(subset=[x_key, y_key]).copy()

    fig = px.bar(
        df,
        x=y_key,
        y=x_key,
        orientation="h",
        title=title,
        color=x_key,
        color_discrete_sequence=COLORWAY,
    )
    fig.update_layout(
        margin=dict(l=180, r=40, t=50, b=70),
        height=420,
        title=dict(font=dict(size=16)),
        xaxis=dict(tickfont=dict(size=11), automargin=True, ticklabeloverflow="allow"),
        yaxis=dict(automargin=True, tickfont=dict(size=11)),
        showlegend=False,
    )
    fig.update_traces(hovertemplate=f"%{{y}}<br>%{{x:,}} {value_label}<extra></extra>")
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": False, "responsive": True})


def _donut_chart(items: list[dict[str, Any]], label_key: str, value_key: str, *, title: str) -> str:
    df = pd.DataFrame(items)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig.to_html(include_plotlyjs=False, full_html=False)

    df[value_key] = pd.to_numeric(df[value_key], errors="coerce")
    df = df.dropna(subset=[label_key, value_key]).copy()

    fig = px.pie(df, names=label_key, values=value_key, hole=0.55, title=title, color_discrete_sequence=COLORWAY)
    fig.update_layout(
        margin=dict(l=10, r=40, t=50, b=70),
        height=360,
        legend_title_text="",
        title=dict(font=dict(size=16)),
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": False, "responsive": True})


def _cpc_label(section: str | None) -> str:
    if not section:
        return "Unknown"
    meaning = CPC_SECTION_LABELS.get(section)
    return meaning if meaning else section


def _trend_chart(df: pd.DataFrame, *, title: str) -> str:
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig.to_html(include_plotlyjs=False, full_html=False)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["patents"],
            mode="lines",
            name="Patents",
            hovertemplate="%{x}: %{y:,}<extra></extra>",
        )
    )

    if "rolling_5yr_avg" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=df["rolling_5yr_avg"],
                mode="lines",
                name="5yr avg",
                line=dict(dash="dot"),
                hovertemplate="%{x}: %{y:,}<extra></extra>",
            )
        )

    fig.update_layout(
        title=title,
        margin=dict(l=40, r=40, t=50, b=70),
        height=420,
        xaxis=dict(
            rangeslider=dict(visible=True),
            type="linear",
            tickfont=dict(size=11),
            automargin=True,
            ticklabeloverflow="allow",
        ),
        yaxis=dict(tickformat=",", tickfont=dict(size=11)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title_font=dict(size=16),
        colorway=COLORWAY,
    )

    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": False, "responsive": True})


def _comparison_trend_chart(
    items: list[dict[str, Any]],
    series: list[tuple[str, str]],
    *,
    title: str,
) -> str:
    df = pd.DataFrame(items)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return fig.to_html(include_plotlyjs=False, full_html=False)

    df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
    for _, key in series:
        df[key] = pd.to_numeric(df.get(key), errors="coerce")

    df = df.dropna(subset=["year"]).copy()
    fig = go.Figure()
    for label, key in series:
        if key not in df.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=df["year"],
                y=df[key],
                mode="lines",
                name=label,
                hovertemplate="%{x}: %{y:,}<extra></extra>",
            )
        )

    fig.update_layout(
        title=title,
        margin=dict(l=40, r=40, t=50, b=70),
        height=360,
        xaxis=dict(tickfont=dict(size=11), automargin=True, ticklabeloverflow="allow"),
        yaxis=dict(tickformat=",", tickfont=dict(size=11)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title_font=dict(size=16),
        colorway=COLORWAY,
    )
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": False, "responsive": True})


def _cpc_sections_chart(cpc_report: dict[str, Any]) -> str:
    items = cpc_report.get("cpc_sections", []) if cpc_report else []
    df = pd.DataFrame(items)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="Patent Categories (CPC sections)")
        return fig.to_html(include_plotlyjs=False, full_html=False)

    df["patents"] = pd.to_numeric(df.get("patents"), errors="coerce")
    df = df.dropna(subset=["cpc_section", "patents"]).copy()
    df["cpc_section_label"] = df["cpc_section"].map(_cpc_label)
    df = df.sort_values("patents", ascending=True)

    fig = px.bar(
        df,
        x="patents",
        y="cpc_section_label",
        orientation="h",
        title="Patent Categories (CPC sections)",
        color_discrete_sequence=COLORWAY,
    )
    fig.update_layout(margin=dict(l=180, r=40, t=50, b=70), height=360, title_font=dict(size=16))
    fig.update_traces(hovertemplate="%{y}<br>%{x:,} patents<extra></extra>")
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": False, "responsive": True})


def _cpc_growth_by_decade_chart(cpc_report: dict[str, Any]) -> str:
    items = cpc_report.get("cpc_growth_by_decade", []) if cpc_report else []
    df = pd.DataFrame(items)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="CPC section growth by decade")
        return fig.to_html(include_plotlyjs=False, full_html=False)

    df["decade"] = pd.to_numeric(df.get("decade"), errors="coerce")
    df["patents"] = pd.to_numeric(df.get("patents"), errors="coerce")
    df = df.dropna(subset=["cpc_section", "decade", "patents"]).copy()
    df["decade"] = df["decade"].astype(int)
    df = df[df["decade"] >= MIN_DASHBOARD_YEAR]
    df = df.sort_values(["decade", "cpc_section"])
    df["cpc_section_label"] = df["cpc_section"].map(_cpc_label)

    fig = px.area(
        df,
        x="decade",
        y="patents",
        color="cpc_section_label",
        title="CPC section growth by decade",
        color_discrete_sequence=COLORWAY,
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=50, b=70),
        height=420,
        yaxis=dict(tickformat=",", tickfont=dict(size=11)),
        xaxis=dict(tickfont=dict(size=11), automargin=True, ticklabeloverflow="allow"),
        title_font=dict(size=16),
    )
    fig.update_traces(hovertemplate="%{x}s<br>%{y:,} patents<extra></extra>")
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": False, "responsive": True})


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.get("/")
    def dashboard() -> str:
        report = load_report()
        weighted_report = load_weighted_report()
        displacement_report = load_displacement_report()
        geopolitical_report = load_geopolitical_report()
        ibm_vs_samsung = load_ibm_vs_samsung()
        media_streaming_vs_optical = load_media_streaming_vs_optical()
        energy_renewables_vs_fossil = load_energy_renewables_vs_fossil()
        energy_battery_vs_oil = load_energy_battery_vs_oil()
        df_trends = trends_df(report)

        if not df_trends.empty:
            default_start = max(MIN_DASHBOARD_YEAR, int(df_trends["year"].min()))
            default_end = int(df_trends["year"].max())
        else:
            default_start, default_end = MIN_DASHBOARD_YEAR, 2024

        start_year = _parse_int(request.args.get("start_year"), default=default_start)
        end_year = _parse_int(request.args.get("end_year"), default=default_end)

        # clamp/swap
        if start_year > end_year:
            start_year, end_year = end_year, start_year

        start_year = max(start_year, default_start, MIN_DASHBOARD_YEAR)
        end_year = min(end_year, default_end)

        filters = DashboardFilters(start_year=start_year, end_year=end_year)
        filtered = apply_filters(df_trends, filters)

        cpc_report = cpc_payload(report)
        charts = {
            "trend": _trend_chart(filtered, title="Patents Over Time"),
            "top_companies_raw": _bar_chart(
                report.get("top_companies", []),
                "name",
                "patents",
                title="Top Companies (Raw Count)",
            ),
            "top_companies_weighted": _bar_chart(
                weighted_report.get("weighted_companies_citations", []),
                "name",
                "avg_citations_per_patent",
                title="Top Companies (Avg Citations per Patent)",
                value_label="avg citations per patent",
            ),
            "top_inventors_raw": _bar_chart(
                report.get("top_inventors", []),
                "name",
                "patents",
                title="Top Inventors (Raw Count)",
            ),
            "top_inventors_weighted": _bar_chart(
                weighted_report.get("weighted_inventors_hindex", []),
                "name",
                "h_index",
                title="Top Inventors (H-Index)",
                value_label="h-index",
            ),
            "ibm_vs_samsung": _comparison_trend_chart(
                ibm_vs_samsung,
                [
                    ("IBM", "ibm_patents"),
                    ("Samsung", "samsung_patents"),
                ],
                title="IBM vs Samsung (Patent Counts)",
            ),
            "top_countries": _donut_chart(report.get("top_countries", []), "country", "patents", title="Top Countries (by patent count)"),
            "diag_smartphones_vs_telephony": _comparison_trend_chart(
                displacement_report.get("diag_smartphones_vs_telephony", []),
                [
                    ("Wireless (H04W)", "wireless_patents"),
                    ("Telephony (H04M)", "telephony_patents"),
                ],
                title="Smartphones vs Telephony",
            ),
            "diag_ev_vs_combustion": _comparison_trend_chart(
                displacement_report.get("diag_ev_vs_combustion", []),
                [
                    ("EV (B60L)", "ev_patents"),
                    ("Combustion (F02D/F02M)", "combustion_patents"),
                ],
                title="EV vs Combustion",
            ),
            "diag_ai_vs_software": _comparison_trend_chart(
                displacement_report.get("diag_ai_vs_software", []),
                [
                    ("AI (G06N)", "ai_patents"),
                    ("Software (G06F)", "software_patents"),
                ],
                title="AI vs Traditional Software",
            ),
            "trend_streaming_vs_optical": _comparison_trend_chart(
                media_streaming_vs_optical,
                [
                    ("Streaming", "streaming_patents"),
                    ("Optical Discs", "optical_disc_patents"),
                ],
                title="Death of Physical Media: Streaming vs Optical Discs",
            ),
            "trend_renewables_vs_fossil": _comparison_trend_chart(
                energy_renewables_vs_fossil,
                [
                    ("Renewables", "total_renewable_patents"),
                    ("Fossil Extraction", "fossil_extraction_patents"),
                ],
                title="Renewables vs Fossil Fuel Extraction",
            ),
            "trend_battery_vs_oil": _comparison_trend_chart(
                energy_battery_vs_oil,
                [
                    ("Battery Storage", "battery_patents"),
                    ("Oil Extraction", "oil_extraction_patents"),
                ],
                title="Battery Storage vs Oil Extraction",
            ),
            "geo_us_vs_china_overall": _comparison_trend_chart(
                geopolitical_report.get("geo_us_vs_china_overall", []),
                [
                    ("United States", "us_patents"),
                    ("China", "cn_patents"),
                ],
                title="US vs China (Overall Patents)",
            ),
            "geo_korea_vs_japan_h01l": _comparison_trend_chart(
                geopolitical_report.get("geo_korea_vs_japan_h01l", []),
                [
                    ("Japan (H01L)", "jp_h01l"),
                    ("Korea (H01L)", "kr_h01l"),
                ],
                title="Korea vs Japan (Semiconductors H01L)",
            ),
            "geo_trade_war_semiconductors": _comparison_trend_chart(
                geopolitical_report.get("geo_trade_war_semiconductors", []),
                [
                    ("United States", "us_h01l"),
                    ("China", "cn_h01l"),
                    ("Korea", "kr_h01l"),
                    ("Taiwan", "tw_h01l"),
                    ("Japan", "jp_h01l"),
                ],
                title="Semiconductors H01L (Trade War Era)",
            ),
            "cpc_sections": _cpc_sections_chart(cpc_report),
        }

        tables = {
            "inventor_company_pairs": report.get("inventor_company_pairs", []),
            "top_inventor_per_country": report.get("top_inventor_per_country", []),
            "cpc_top_companies": load_cpc_top_companies(),
        }

        cpc_legend = [
            {"meaning": CPC_SECTION_LABELS[section]}
            for section in sorted(CPC_SECTION_LABELS.keys())
        ]

        return render_template(
            "dashboard.html",
            last_updated=report_last_updated(),
            filters=filters,
            year_min=default_start,
            year_max=default_end,
            kpis=kpis(report, filtered),
            charts=charts,
            tables=tables,
            cpc_legend=cpc_legend,
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    # For local dev only.
    app.run(host="127.0.0.1", port=5000, debug=True)
