"""
dashboard/data_loader.py
=========================
Loads gold-layer Parquet files for the dashboard.
Falls back gracefully if files are missing (re-runs silver/gold pipeline).
"""

import json
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import GOLD_DIR


def _load_parquet(filename: str) -> pd.DataFrame | None:
    path = GOLD_DIR / filename
    if path.exists():
        try:
            df = pd.read_parquet(path)
            logger.debug("Loaded {} — {} rows", filename, len(df))
            return df
        except Exception as e:
            logger.error("Failed to load {}: {}", filename, e)
    return None


def load_all() -> dict:
    """Load all gold datasets. Returns dict of DataFrames + KPI dict."""
    data = {}

    data["eu_annual"]         = _load_parquet("eu_annual.parquet")
    data["country_powertrain_annual"] = _load_parquet("country_powertrain_annual.parquet")
    data["country_bev_share"] = _load_parquet("country_bev_share.parquet")
    data["market_value"]      = _load_parquet("market_value.parquet")
    data["forecast"]          = _load_parquet("forecast_scenarios.parquet")

    # KPI snapshot
    kpi_path = GOLD_DIR / "kpi_snapshot.json"
    if kpi_path.exists():
        with open(kpi_path) as fh:
            data["kpi"] = json.load(fh)
    else:
        data["kpi"] = {}

    # If gold is empty, run pipeline on-demand
    if data["eu_annual"] is None:
        logger.warning("Gold data missing — running pipeline now …")
        try:
            from pipeline.gold import run_gold
            from pipeline.silver import run_silver
            run_silver()
            run_gold()
            # Retry
            data["eu_annual"]         = _load_parquet("eu_annual.parquet")
            data["country_powertrain_annual"] = _load_parquet("country_powertrain_annual.parquet")
            data["country_bev_share"] = _load_parquet("country_bev_share.parquet")
            data["market_value"]      = _load_parquet("market_value.parquet")
            data["forecast"]          = _load_parquet("forecast_scenarios.parquet")
            kpi_path = GOLD_DIR / "kpi_snapshot.json"
            if kpi_path.exists():
                with open(kpi_path) as fh:
                    data["kpi"] = json.load(fh)
        except Exception as e:
            logger.error("On-demand pipeline failed: {}", e)

    return data
