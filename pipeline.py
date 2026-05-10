import argparse
import subprocess
import sys

from clean import run_clean
from download import run_download
from load import run_load


ANALYSIS_SCRIPTS = {
    "core": "analysis_01_core.py",
    "cpc": "analysis_02_cpc.py",
    "weighted": "analysis_03_weighted.py",
    "displacement": "analysis_04_displacement.py",
    "geopolitical": "analysis_05_geopolitical.py",
    "trends": "analysis_06_trends.py",
    "country": "analysis_07_country.py",
    "company": "analysis_08_company.py",
    "fin": "analysis_09_fin.py",
    "trend-other": "analysis_10_trend_other.py",
}

ANALYSIS_ORDER = [
    "core",
    "cpc",
    "weighted",
    "displacement",
    "geopolitical",
    "trends",
    "country",
    "company",
    "fin",
    "trend-other",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the patents data pipeline.")
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip running analysis (pipeline only).",
    )
    parser.add_argument(
        "--analysis",
        help=(
            "Comma-separated analysis keys to run (default: all). "
            "Options: core,cpc,weighted,displacement,geopolitical,trends,country,"
            "company,fin,trend-other"
        ),
    )
    args = parser.parse_args()

    run_download()
    run_clean()
    run_load()

    if args.skip_analysis:
        return

    if args.analysis:
        requested = [item.strip() for item in args.analysis.split(",") if item.strip()]
        unknown = [item for item in requested if item not in ANALYSIS_SCRIPTS]
        if unknown:
            raise SystemExit(
                "Unknown analysis key(s): "
                f"{', '.join(unknown)}. Use --analysis with valid keys."
            )
        analysis_keys = requested
    else:
        analysis_keys = ANALYSIS_ORDER

    for key in analysis_keys:
        script = ANALYSIS_SCRIPTS[key]
        print(f"Running {script}...")
        subprocess.run([sys.executable, script], check=True)


if __name__ == "__main__":
    main()
