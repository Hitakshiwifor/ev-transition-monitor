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
    # Primary brand
    "navy":          "#003662",   # WifOR Blau   rgb(0,54,98)
    "red":           "#CC3A45",   # WifOR Rot    rgb(204,58,69)
    "white":         "#FFFFFF",
    # Screen secondary palette
    "teal":          "#77C6BE",   # Petrol       rgb(119,198,190)
    "teal_mid":      "#83B6EF",   # Hellblau     rgb(131,182,239)
    "teal_light":    "#A5CD71",   # Grün         rgb(165,205,113)
    "teal_pale":     "#F4F8FA",   # Near-white background
    "orange":        "#F48D40",   # Orange       rgb(244,141,64)
    "orange_light":  "#FEF0E4",   # Light orange tint
    "yellow":        "#DBCA71",   # Gelb         rgb(219,202,113)
    "pink":          "#FC6775",   # Pink         rgb(252,103,117)
    # Greys
    "grey1":         "#D9D9D9",   # Grau 1
    "grey2":         "#BFBFBF",   # Grau 2
    "grey3":         "#A6A6A6",   # Grau 3
    "grey4":         "#7F7F7F",   # Grau 4
    # UI tokens
    "bg_light":      "#F4F8FA",
    "text_dark":     "#003662",   # WifOR navy for headings
    "text_muted":    "#7F7F7F",   # Grau 4
    "border":        "#D9D9D9",   # Grau 1
    # Powertrain palette — consistent across ALL charts
    "bev":           "#003662",   # BEV        → WifOR Blau
    "phev":          "#77C6BE",   # PHEV       → Petrol
    "hev":           "#83B6EF",   # HEV        → Hellblau
    "ice_petrol":    "#F48D40",   # ICE Petrol → Orange
    "ice_diesel":    "#CC3A45",   # ICE Diesel → Rot
    "other":         "#A6A6A6",   # Other      → Grau 3
}

# ── EU Countries of interest ─────────────────────────────────
FORECAST_SOURCE_COLORS = {
    "IEA Global EV Outlook 2025 - STEPS": "#003662",
    "ACEA latest EU actual": "#F48D40",
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
