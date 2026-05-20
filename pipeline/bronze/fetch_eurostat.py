"""
pipeline/bronze/fetch_eurostat.py
==================================
Bronze layer — Fetches raw car-registration data from the
Eurostat JSON API and saves it unchanged to data/bronze/.

Datasets used
─────────────
• road_eqr_carpda  → Annual new passenger cars by fuel/powertrain type
• road_eqr_carm    → Monthly total new passenger car registrations

Medallion role : RAW — no transformation, no filtering.
Output         : data/bronze/eurostat_<dataset>_<YYYYMMDD>.json
"""

import json
import requests
from datetime import datetime
from pathlib import Path
from loguru import logger

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import (
    BRONZE_DIR,
    EUROSTAT_BASE_URL,
    EUROSTAT_DATASET_ANNUAL,
    EUROSTAT_DATASET_MONTHLY,
    EUROSTAT_TIMEOUT_SEC,
    EUROPE_GEOJSON_URL,
    GEOJSON_DIR,
)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _build_url(dataset: str, extra_params: dict = None) -> str:
    params = {"format": "JSON", "lang": "EN"}
    if extra_params:
        params.update(extra_params)
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{EUROSTAT_BASE_URL}/{dataset}?{qs}"


def _fetch_json(url: str, dataset_label: str) -> dict:
    logger.info("Fetching {} from Eurostat …", dataset_label)
    logger.debug("URL: {}", url)
    try:
        resp = requests.get(url, timeout=EUROSTAT_TIMEOUT_SEC)
        resp.raise_for_status()
        data = resp.json()
        logger.success(
            "Received {} bytes for {}", len(resp.content), dataset_label
        )
        return data
    except requests.exceptions.Timeout:
        logger.error("Timeout fetching {}", dataset_label)
        raise
    except requests.exceptions.HTTPError as e:
        logger.error("HTTP {} for {}: {}", e.response.status_code, dataset_label, e)
        raise
    except Exception as e:
        logger.error("Unexpected error fetching {}: {}", dataset_label, e)
        raise


def _save_bronze(data: dict, dataset: str) -> Path:
    today = datetime.utcnow().strftime("%Y%m%d")
    out_path = BRONZE_DIR / f"eurostat_{dataset}_{today}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    logger.info("Saved bronze file → {}", out_path.name)
    return out_path


# ─────────────────────────────────────────────────────────────
# Public pipeline steps
# ─────────────────────────────────────────────────────────────

def fetch_annual_registrations_by_powertrain() -> Path:
    """
    Fetch annual new passenger car registrations split by
    fuel/powertrain type for all EU+EFTA countries.
    Dataset: road_eqr_carpda
    """
    url = _build_url(EUROSTAT_DATASET_ANNUAL)
    data = _fetch_json(url, "road_eqr_carpda (annual by powertrain)")
    return _save_bronze(data, EUROSTAT_DATASET_ANNUAL)


def fetch_monthly_registrations() -> Path:
    """
    Fetch monthly total new passenger car registrations.
    Dataset: road_eqr_carm
    """
    url = _build_url(EUROSTAT_DATASET_MONTHLY)
    data = _fetch_json(url, "road_eqr_carm (monthly totals)")
    return _save_bronze(data, EUROSTAT_DATASET_MONTHLY)


def fetch_europe_geojson() -> Path:
    """
    Download Europe GeoJSON for the choropleth map.
    Cached locally — only re-downloads if not already present.
    """
    out_path = GEOJSON_DIR / "europe.geojson"
    if out_path.exists():
        logger.info("GeoJSON already cached at {}", out_path.name)
        return out_path

    logger.info("Downloading Europe GeoJSON …")
    try:
        resp = requests.get(EUROPE_GEOJSON_URL, timeout=30)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
        logger.success("GeoJSON saved → {}", out_path.name)
    except Exception as e:
        logger.warning("Could not download GeoJSON ({}). Map will use built-in.", e)

    return out_path


# ─────────────────────────────────────────────────────────────
# Run all bronze steps
# ─────────────────────────────────────────────────────────────

def run_bronze() -> dict:
    """Execute all bronze ingestion steps. Returns paths dict."""
    logger.info("=== BRONZE LAYER START ===")
    results = {}

    try:
        results["annual"] = fetch_annual_registrations_by_powertrain()
    except Exception as e:
        logger.error("Bronze annual fetch failed: {}", e)
        results["annual"] = None

    try:
        results["monthly"] = fetch_monthly_registrations()
    except Exception as e:
        logger.error("Bronze monthly fetch failed: {}", e)
        results["monthly"] = None

    try:
        results["geojson"] = fetch_europe_geojson()
    except Exception as e:
        logger.warning("Bronze GeoJSON fetch failed: {}", e)
        results["geojson"] = None

    logger.info("=== BRONZE LAYER COMPLETE ===")
    return results


if __name__ == "__main__":
    from config.logging_config import setup_logging
    from config.settings import LOG_DIR
    setup_logging(LOG_DIR)
    run_bronze()
