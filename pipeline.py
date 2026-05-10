import argparse

from clean import run_clean
from download import run_download
from load import run_load


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the patents data pipeline.")
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip running analysis (pipeline only).",
    )
    args = parser.parse_args()

    run_download()
    run_clean()
    run_load()

    if not args.skip_analysis:
        print("Analysis hooks not wired yet. Use analysis scripts directly for now.")


if __name__ == "__main__":
    main()
