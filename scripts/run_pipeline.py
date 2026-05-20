"""
scripts/run_pipeline.py
========================
Entry point to run the full medallion pipeline:
  Bronze → Silver → Gold

Run with:  uv run python scripts/run_pipeline.py
           uv run python scripts/run_pipeline.py --layer silver
           uv run python scripts/run_pipeline.py --layer gold
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.logging_config import setup_logging
from config.settings import LOG_DIR
from pipeline.bronze import run_bronze
from pipeline.silver import run_silver
from pipeline.gold   import run_gold

setup_logging(LOG_DIR)

from loguru import logger


def main(layer: str = "all") -> None:
    logger.info("Pipeline started — layer={}", layer)

    if layer in ("all", "bronze"):
        logger.info("── Running Bronze ──────────────────────────────────")
        run_bronze()

    if layer in ("all", "silver"):
        logger.info("── Running Silver ──────────────────────────────────")
        run_silver()

    if layer in ("all", "gold"):
        logger.info("── Running Gold ────────────────────────────────────")
        run_gold()

    logger.success("Pipeline complete ✓")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run EV Transition Monitor pipeline")
    parser.add_argument(
        "--layer",
        choices=["all", "bronze", "silver", "gold"],
        default="all",
        help="Which medallion layer to run (default: all)",
    )
    args = parser.parse_args()
    main(args.layer)
