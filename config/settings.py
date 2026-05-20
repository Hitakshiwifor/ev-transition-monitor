"""
config/settings.py
==================
Central configuration for the European EV Transition Monitor.
All environment-overridable settings live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Project root ────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent

# ── Data layer paths (Medallion Architecture) ───────────────
DATA_DIR    = ROOT_DIR / "data"
BRONZE_DIR  = DATA_DIR / "bronze"
SILVER_DIR  = DATA_DIR / "silver"
GOLD_DIR    = DATA_DIR / "gold"
GEOJSON_DIR = ROOT_DIR / "geojson"
LOG_DIR     = ROOT_DIR / "logs"

# Ensure directories exist at import time
for _d in (BRONZE_DIR, SILVER_DIR, GOLD_DIR, GEOJSON_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── Eurostat API ─────────────────────────────────────────────
EUROSTAT_BASE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
)
# Car registrations by fuel/powertrain type, annual
EUROSTAT_DATASET_ANNUAL   = "road_eqr_carpda"
# Monthly registrations (total, used for YoY trend)
EUROSTAT_DATASET_MONTHLY  = "road_eqr_carm"

EUROSTAT_TIMEOUT_SEC = 30

# ── GeoJSON ──────────────────────────────────────────────────
EUROPE_GEOJSON_URL = (
    "https://raw.githubusercontent.com/leakyMirror/map-of-europe/"
    "master/GeoJSON/europe.geojson"
)

# ── Dashboard ────────────────────────────────────────────────
DASH_HOST    = os.getenv("DASH_HOST", "127.0.0.1")
DASH_PORT    = int(os.getenv("DASH_PORT", 8050))
DASH_DEBUG   = os.getenv("DASH_DEBUG", "false").lower() == "true"

# ── WifOR Brand Colours ──────────────────────────────────────
WIFOR_COLORS = {
    "navy":          "#003A5D",   # Primary deep navy
    "teal":          "#00929A",   # WifOR signature teal
    "teal_mid":      "#47B8BE",   # Medium teal
    "teal_light":    "#A8DEE0",   # Light teal
    "teal_pale":     "#E4F5F6",   # Very light teal background
    "orange":        "#F07800",   # Accent orange
    "orange_light":  "#FFE8CC",   # Light orange tint
    "white":         "#FFFFFF",
    "bg_light":      "#F4F8FA",   # Page background
    "text_dark":     "#1A2B3C",   # Primary text
    "text_muted":    "#6B8090",   # Secondary / muted text
    "border":        "#D8E6EA",   # Subtle border
    # Powertrain palette (consistent across all charts)
    "bev":           "#00929A",   # BEV → WifOR teal
    "phev":          "#47B8BE",   # PHEV → medium teal
    "hev":           "#A8DEE0",   # HEV → light teal
    "ice_petrol":    "#F07800",   # Petrol ICE → orange
    "ice_diesel":    "#B05800",   # Diesel ICE → dark orange
    "other":         "#6B8090",   # Other → muted
}

# ── EU Countries of interest ─────────────────────────────────
FORECAST_SOURCE_COLORS = {
    "IEA Global EV Outlook 2025 - STEPS": "#003A5D",
    "ACEA latest EU actual": "#F07800",
}

EU_COUNTRIES = {
    "AT": "Austria",      "BE": "Belgium",     "BG": "Bulgaria",
    "CY": "Cyprus",       "CZ": "Czechia",     "DE": "Germany",
    "DK": "Denmark",      "EE": "Estonia",     "EL": "Greece",
    "ES": "Spain",        "FI": "Finland",     "FR": "France",
    "HR": "Croatia",      "HU": "Hungary",     "IE": "Ireland",
    "IT": "Italy",        "LT": "Lithuania",   "LU": "Luxembourg",
    "LV": "Latvia",       "MT": "Malta",       "NL": "Netherlands",
    "PL": "Poland",       "PT": "Portugal",    "RO": "Romania",
    "SE": "Sweden",       "SI": "Slovenia",    "SK": "Slovakia",
    # EFTA / associated
    "NO": "Norway",       "IS": "Iceland",     "CH": "Switzerland",
    "UK": "United Kingdom",
}
