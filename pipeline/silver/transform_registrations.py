"""
pipeline/silver/transform_registrations.py
==========================================
Silver layer — Cleans and standardises raw data from multiple bronze sources
into analytics-ready Parquet files.

Source priority
───────────────
1. Eurostat road_eqr_carpda  → Full powertrain breakdown by country × year
2. Our World in Data CSV     → BEV+PHEV share validation / gap-fill
3. ACEA JSON                 → Latest total registrations metadata

No hardcoded fallback values. If all sources are unavailable, a
DataUnavailableError is raised with a clear message instructing the user
to run the pipeline with network access.

Medallion role : CLEAN — validated, typed, documented.
Output         : data/silver/registrations_annual.parquet
                 data/silver/registrations_by_country.parquet
                 data/silver/owid_ev_share.parquet          (if OWID available)
                 data/silver/forecast_scenarios.parquet
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import BRONZE_DIR, EU_COUNTRIES, SILVER_DIR


# ─────────────────────────────────────────────────────────────
# Custom exception
# ─────────────────────────────────────────────────────────────

class DataUnavailableError(RuntimeError):
    """Raised when no real data source is available for silver processing."""
    pass


# ─────────────────────────────────────────────────────────────
# Eurostat mot_nrg code → powertrain label
# Derived from actual API response (mot_nrg dimension)
# ─────────────────────────────────────────────────────────────

# IMPORTANT: Use the most granular codes to avoid double-counting.
# - PET_X_HYB  = pure petrol ICE (petrol EXCLUDING hybrids)
# - DIE_X_HYB  = pure diesel ICE (diesel EXCLUDING hybrids)
# - PET / DIE  = petrol/diesel INCLUDING hybrids → SKIP (would double-count)
# - ELC        = Battery Electric (BEV only)
# - ELC_PET_PI = Plug-in Hybrid Petrol-Electric (PHEV)
# - ELC_DIE_PI = Plug-in Hybrid Diesel-Electric (PHEV)
# - ELC_PET_HYB = Full Hybrid Petrol-Electric (HEV, non-plug-in)
# - ELC_DIE_HYB = Full Hybrid Diesel-Electric (HEV, non-plug-in)

FUEL_LABEL_MAP: dict[str, str | None] = {
    # ── Battery Electric ──────────────────────────────────────
    "ELC":          "BEV",

    # ── Plug-in Hybrids (PHEV) ───────────────────────────────
    "ELC_PET_PI":   "PHEV",        # Plug-in hybrid petrol-electric
    "ELC_DIE_PI":   "PHEV",        # Plug-in hybrid diesel-electric

    # ── Full Hybrids (HEV, non-plug-in) ─────────────────────
    "ELC_PET_HYB":  "HEV",         # Full hybrid petrol-electric
    "ELC_DIE_HYB":  "HEV",         # Full hybrid diesel-electric

    # ── Pure ICE — EXCLUDING hybrids (use these, not PET/DIE) ─
    "PET_X_HYB":    "ICE_Petrol",  # Petrol excl. hybrids → pure petrol ICE
    "DIE_X_HYB":    "ICE_Diesel",  # Diesel excl. hybrids → pure diesel ICE

    # Aggregate petrol/diesel are used only when granular excl.-hybrid
    # codes are unavailable for the country-year.
    "PET":          "ICE_Petrol",
    "DIE":          "ICE_Diesel",

    # ── Alternative / niche ──────────────────────────────────
    "LPG":          "Other",        # Liquefied petroleum gas
    "GAS":          "Other",        # Natural gas
    "HYD_FCELL":    "Other",        # Hydrogen fuel cell
    "BIOETH":       "Other",        # Bioethanol
    "BIODIE":       "Other",        # Biodiesel
    "BIFUEL":       "Other",        # Bi-fuel
    "ALT":          None,           # Aggregate alternative energy, skip to avoid double-counting
    "OTH":          "Other",        # Other

    # ── Aggregate → skip ─────────────────────────────────────
    "TOTAL":        None,
}

# Country codes that are EU/EFTA members we care about
# Eurostat uses EU27_2020 for the EU-27 aggregate
EUROSTAT_EU_AGGREGATE = "EU27_2020"

POWERTRAIN_ORDER = ["BEV", "PHEV", "HEV", "ICE_Petrol", "ICE_Diesel", "Other"]

# Map Eurostat geo codes → our internal codes
GEO_REMAP = {
    "EU27_2020": "EU",   # EU-27 aggregate → "EU"
    "EL":        "EL",   # Greece stays EL (Eurostat convention, matches EU_COUNTRIES)
    "UK":        "UK",   # UK stays UK
}

# ISO-2 → ISO-3 for Plotly choropleth
ISO2_TO_ISO3 = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "CY": "CYP", "CZ": "CZE",
    "DE": "DEU", "DK": "DNK", "EE": "EST", "EL": "GRC", "ES": "ESP",
    "FI": "FIN", "FR": "FRA", "HR": "HRV", "HU": "HUN", "IE": "IRL",
    "IT": "ITA", "LT": "LTU", "LU": "LUX", "LV": "LVA", "MT": "MLT",
    "NL": "NLD", "PL": "POL", "PT": "PRT", "RO": "ROU", "SE": "SWE",
    "SI": "SVN", "SK": "SVK", "NO": "NOR", "IS": "ISL", "CH": "CHE",
    "UK": "GBR", "GB": "GBR", "LI": "LIE",
}

# Countries to include in dashboard (EU members + key EFTA)
INCLUDE_COUNTRIES = set(EU_COUNTRIES.keys()) | {"EU", "LI"}
EU_MEMBER_CODES = set(EU_COUNTRIES.keys()) - {"NO", "IS", "CH", "UK"}


# ─────────────────────────────────────────────────────────────
# Bronze file helpers
# ─────────────────────────────────────────────────────────────

def _latest_bronze(pattern: str) -> Path | None:
    files = sorted(BRONZE_DIR.glob(pattern))
    if not files:
        return None
    return files[-1]


# ═════════════════════════════════════════════════════════════
# SOURCE 1: Eurostat JSON → tidy DataFrame
# ═════════════════════════════════════════════════════════════

def _parse_eurostat_json(raw: dict) -> pd.DataFrame:
    """
    Parse Eurostat JSON-stat sparse format into a flat DataFrame.
    Correctly handles the actual road_eqr_carpda dimension structure:
    freq × unit × mot_nrg × geo × time
    """
    ids    = raw.get("id", [])
    size   = raw.get("size", [])
    dims   = raw.get("dimension", {})
    values = raw.get("value", {})

    # Build per-dimension lookup: position → code
    dim_info = {}
    for dim_id in ids:
        cats = dims[dim_id]["category"]
        idx  = cats.get("index", {})
        lbl  = cats.get("label", {})
        if isinstance(idx, dict):
            pos_to_code = {v: k for k, v in idx.items()}
        else:
            pos_to_code = {i: c for i, c in enumerate(idx)}
        dim_info[dim_id] = {"pos_to_code": pos_to_code, "code_to_label": lbl}

    # Compute strides for index arithmetic
    n = len(ids)
    strides = [1] * n
    for i in range(n - 2, -1, -1):
        strides[i] = strides[i + 1] * size[i + 1]

    rows = []
    for str_idx, val in values.items():
        flat = int(str_idx)
        row  = {}
        rem  = flat
        for i, dim_id in enumerate(ids):
            pos  = rem // strides[i]
            rem  = rem  % strides[i]
            code = dim_info[dim_id]["pos_to_code"].get(pos, str(pos))
            row[dim_id] = code
        row["value"] = val
        rows.append(row)

    return pd.DataFrame(rows)


def transform_eurostat() -> pd.DataFrame | None:
    """
    Parse Eurostat road_eqr_carpda bronze JSON.
    Returns tidy DataFrame or None if file missing / unparseable.
    """
    path = _latest_bronze("eurostat_road_eqr_carpda_*.json")
    if path is None:
        logger.warning("No Eurostat bronze file found")
        return None

    logger.info("Transforming Eurostat data from {} …", path.name)
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception as e:
        logger.error("Could not read Eurostat JSON: {}", e)
        return None

    df = _parse_eurostat_json(raw)

    if df.empty:
        logger.error("Eurostat parse produced empty DataFrame")
        return None

    logger.debug("Raw Eurostat parse: {} rows, cols: {}", len(df), df.columns.tolist())

    # ── Remap columns ────────────────────────────────────────
    # Columns after parse: freq, unit, mot_nrg, geo, time, value
    df = df.rename(columns={
        "mot_nrg": "fuel_code",
        "geo":     "country_code",
        "time":    "year",
    })

    # ── Map fuel codes → powertrain labels ──────────────────
    df["powertrain"] = df["fuel_code"].map(FUEL_LABEL_MAP)
    # None means skip (aggregated or double-count codes)
    df = df.dropna(subset=["powertrain"])
    df = df[df["powertrain"] != "skip"]

    # ── Remap country codes ──────────────────────────────────
    df["country_code"] = df["country_code"].replace(GEO_REMAP)

    # ── Filter to relevant countries ────────────────────────
    df = df[df["country_code"].isin(INCLUDE_COUNTRIES)].copy()

    # ── Types ────────────────────────────────────────────────
    df["year"]          = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["registrations"] = pd.to_numeric(df["value"], errors="coerce").fillna(0).astype(int)
    df = df[df["registrations"] > 0]

    code_sets = df.groupby(["country_code", "year"])["fuel_code"].transform(
        lambda s: "|".join(sorted(set(s)))
    )
    has_pure_petrol = code_sets.str.contains("PET_X_HYB", regex=False)
    has_pure_diesel = code_sets.str.contains("DIE_X_HYB", regex=False)
    df = df[
        ~(
            ((df["fuel_code"] == "PET") & has_pure_petrol)
            | ((df["fuel_code"] == "DIE") & has_pure_diesel)
        )
    ].copy()

    # ── Aggregate (multiple fuel codes → same powertrain label) ─
    df = df.groupby(
        ["country_code", "year", "powertrain"], as_index=False
    )["registrations"].sum()

    # ── Add country names ────────────────────────────────────
    eu_aggregate = df[df["country_code"].isin(EU_MEMBER_CODES)].groupby(
        ["year", "powertrain"], as_index=False
    )["registrations"].sum()
    eu_aggregate["country_code"] = "EU"
    df = pd.concat([df[df["country_code"] != "EU"], eu_aggregate], ignore_index=True)

    country_names = {**EU_COUNTRIES, "EU": "European Union (EU-27)", "LI": "Liechtenstein"}
    df["country_name"] = df["country_code"].map(country_names).fillna(df["country_code"])

    # ── Compute market share within country × year ───────────
    totals = df.groupby(["country_code", "year"])["registrations"].transform("sum")
    df["share_pct"] = (df["registrations"] / totals * 100).round(2)

    # ── Categorical ordering ─────────────────────────────────
    df["powertrain"] = pd.Categorical(df["powertrain"], categories=POWERTRAIN_ORDER, ordered=True)
    df.sort_values(["country_code", "year", "powertrain"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df["source"] = "Eurostat road_eqr_carpda"

    # Quick sanity log
    eu_2024 = df[(df["country_code"] == "EU") & (df["year"] == 2024)]
    if not eu_2024.empty:
        for _, row in eu_2024.iterrows():
            logger.debug("  EU 2024 | {:12s} | {:>10,} regs | {:5.1f}%",
                         row["powertrain"], row["registrations"], row["share_pct"])

    logger.success("Eurostat transform: {} rows, {} countries, years {}-{}",
                   len(df),
                   df["country_code"].nunique(),
                   int(df["year"].min()),
                   int(df["year"].max()))
    return df


# ═════════════════════════════════════════════════════════════
# SOURCE 2: Our World in Data CSV → BEV+PHEV share
# ═════════════════════════════════════════════════════════════

# OWID country name → ISO-2 code
OWID_COUNTRY_MAP = {
    "European Union (27)":    "EU",
    "Germany":                "DE",
    "France":                 "FR",
    "Italy":                  "IT",
    "Spain":                  "ES",
    "Netherlands":            "NL",
    "Poland":                 "PL",
    "Belgium":                "BE",
    "Sweden":                 "SE",
    "Austria":                "AT",
    "Denmark":                "DK",
    "Finland":                "FI",
    "Portugal":               "PT",
    "Czechia":                "CZ",
    "Czech Republic":         "CZ",
    "Romania":                "RO",
    "Hungary":                "HU",
    "Slovakia":               "SK",
    "Bulgaria":               "BG",
    "Croatia":                "HR",
    "Slovenia":               "SI",
    "Lithuania":              "LT",
    "Latvia":                 "LV",
    "Estonia":                "EE",
    "Luxembourg":             "LU",
    "Ireland":                "IE",
    "Greece":                 "EL",
    "Cyprus":                 "CY",
    "Malta":                  "MT",
    "Norway":                 "NO",
    "Iceland":                "IS",
    "Switzerland":            "CH",
    "United Kingdom":         "UK",
    "Liechtenstein":          "LI",
}


def transform_owid() -> pd.DataFrame | None:
    """
    Parse Our World in Data EV share CSV.
    Returns DataFrame with country_code, year, ev_share_pct or None.
    """
    path = _latest_bronze("owid_ev_share_*.csv")
    if path is None:
        logger.warning("No OWID EV share file found")
        return None

    logger.info("Transforming OWID EV share data from {} …", path.name)
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except Exception as e:
        logger.error("Could not read OWID CSV: {}", e)
        return None

    logger.debug("OWID raw cols: {}", df.columns.tolist())

    # OWID CSV typically has: Entity, Code, Year, <metric_column>
    # Rename to standard names
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if cl == "entity":
            col_map[col] = "entity"
        elif cl == "code":
            col_map[col] = "iso3"
        elif cl == "year":
            col_map[col] = "year"
        elif "electric" in cl or "ev" in cl or "share" in cl or "plug" in cl:
            col_map[col] = "ev_share_pct"
    df = df.rename(columns=col_map)

    if "ev_share_pct" not in df.columns:
        logger.error("OWID CSV: could not find EV share column. Columns: {}", df.columns.tolist())
        return None

    # Map entity names → ISO-2
    df["country_code"] = df["entity"].map(OWID_COUNTRY_MAP)
    df = df.dropna(subset=["country_code"])

    df["year"]        = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["ev_share_pct"] = pd.to_numeric(df["ev_share_pct"], errors="coerce")
    df = df.dropna(subset=["year", "ev_share_pct"])
    df = df[df["ev_share_pct"] >= 0]

    # Filter to years 2013+ (aligns with Eurostat coverage)
    df = df[df["year"] >= 2013]

    df = df[["country_code", "year", "ev_share_pct"]].copy()
    df["source"] = "Our World in Data (IEA)"

    logger.success("OWID transform: {} rows, {} countries, years {}-{}",
                   len(df),
                   df["country_code"].nunique(),
                   int(df["year"].min()),
                   int(df["year"].max()))
    return df


def transform_acea_passenger_cars() -> pd.DataFrame | None:
    """
    Parse the latest ACEA passenger-car release JSON produced by bronze.
    The ACEA annual release extends the EU aggregate beyond the latest
    annual Eurostat publication without using research-document values.
    """
    path = _latest_bronze("acea_registrations_*.json")
    if path is None:
        logger.warning("No ACEA registration file found")
        return None

    logger.info("Transforming ACEA passenger-car release from {} …", path.name)
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception as e:
        logger.error("Could not read ACEA JSON: {}", e)
        return None

    annual = raw.get("latest_annual")
    if not annual or not annual.get("powertrain") or not annual.get("year"):
        logger.warning("ACEA JSON has no parsed annual passenger-car release")
        return None

    rows = []
    for powertrain, values in annual["powertrain"].items():
        registrations = values.get("registrations")
        share_pct = values.get("share_pct")
        if registrations is None and share_pct is None:
            continue
        rows.append({
            "country_code":  "EU",
            "year":          int(annual["year"]),
            "powertrain":    powertrain,
            "registrations": int(registrations or 0),
            "country_name":  "European Union (EU-27)",
            "share_pct":     round(float(share_pct or 0), 2),
            "source":        "ACEA passenger car registrations",
            "source_url":    annual.get("source_url"),
            "period_type":   annual.get("period_type", "annual"),
        })

    if not rows:
        logger.warning("ACEA annual release parsed but produced no rows")
        return None

    df = pd.DataFrame(rows)
    df["powertrain"] = pd.Categorical(df["powertrain"], categories=POWERTRAIN_ORDER, ordered=True)
    df.sort_values(["country_code", "year", "powertrain"], inplace=True)
    logger.success("ACEA transform: {} rows for {}", len(df), int(df["year"].max()))
    return df


# ═════════════════════════════════════════════════════════════
# Forecast scenarios from IEA Global EV Data Explorer
# ═════════════════════════════════════════════════════════════

def _legacy_research_forecast_df_disabled() -> pd.DataFrame:
    rows = []
    for source, meta in {}.items():
        for year, bev_share in meta["bev_share"].items():
            rows.append({
                "source":        source,
                "year":          year,
                "bev_share_pct": round(bev_share * 100, 1),
                "color":         meta["color"],
            })
    df = pd.DataFrame(rows)
    logger.info("Forecast scenarios table built — {} rows", len(df))
    return df


# ═════════════════════════════════════════════════════════════
# Run all silver steps
# ═════════════════════════════════════════════════════════════

def build_forecast_df(df_annual: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Build forecast/actual share series from source data only.

    Schema: source | year | ev_sales_share_pct | series_type | powertrain | source_url

    Series produced
    ───────────────────────────────────────────────────────────────────────
    powertrain = "BEV+PHEV"  (combined plug-in EV)
      1. EU Observed (Eurostat) — BEV+PHEV share from silver regs. 2013–2024. actual.
      2. IEA Historical (Europe) — IEA EV sales share for Europe.  2010–2024. actual.
      3. IEA STEPS 2025 — STEPS projection, 2025–2029 interpolated. 2024–2030. projection.

    powertrain = "PHEV"
      4. PHEV Observed (Eurostat) — PHEV-only share from silver regs. 2013–2024. actual.
      5. PHEV STEPS 2025 — PHEV projection derived from IEA PHEV/BEV
         sales ratio × total EV share. 2025–2029 interpolated. projection.

    ACEA actual added if parsed (powertrain = "BEV+PHEV").
    ───────────────────────────────────────────────────────────────────────
    NZE / APS not included: the IEA workbook (GEVO_EV_2025) only ships
    Historical + Projection-STEPS for the Europe region.
    HEV not included: IEA does not track non-plug-in hybrids as EVs and
    no free public HEV projection exists for Europe.
    """
    rows: list[dict] = []
    IEA_URL      = "https://www.iea.org/data-and-statistics/data-tools/global-ev-data-explorer"
    EUROSTAT_URL = "https://ec.europa.eu/eurostat"

    def _row(source, year, share, series_type, powertrain, source_url):
        return {
            "source":             source,
            "year":               int(year),
            "ev_sales_share_pct": round(float(share), 2),
            "series_type":        series_type,
            "powertrain":         powertrain,
            "source_url":         source_url,
        }

    def _interpolate_anchors(anchors: pd.Series, yr_from: int, yr_to: int) -> pd.Series:
        """Linear interpolation between anchor points over a full year range."""
        full = pd.Series(index=range(yr_from, yr_to + 1), dtype=float)
        for yr, val in anchors.items():
            if yr_from <= yr <= yr_to:
                full[yr] = float(val)
        return full.interpolate(method="linear")

    # ── Load Eurostat EU registrations ───────────────────────────
    _df_reg = df_annual
    if _df_reg is None:
        _reg_path = SILVER_DIR / "registrations_annual.parquet"
        if _reg_path.exists():
            try:
                _df_reg = pd.read_parquet(_reg_path)
            except Exception as e:
                logger.warning("Could not load silver registrations for forecast: {}", e)

    if _df_reg is not None and not _df_reg.empty:
        df_eu = _df_reg[_df_reg["country_code"] == "EU"].copy()
        if not df_eu.empty:
            total_by_yr = df_eu.groupby("year")["registrations"].sum()

            # ── 1. BEV Observed (Eurostat) ───────────────────────
            bev_by_yr = (
                df_eu[df_eu["powertrain"] == "BEV"]
                .groupby("year")["registrations"].sum()
            )
            for yr, share in (bev_by_yr / total_by_yr * 100).round(2).items():
                rows.append(_row("BEV Observed (Eurostat)", yr, share,
                                 "actual", "BEV", EUROSTAT_URL))
            logger.info("  Forecast: BEV Observed — {} years", len(bev_by_yr))

            # ── 2. PHEV Observed (Eurostat) ──────────────────────
            phev_by_yr = (
                df_eu[df_eu["powertrain"] == "PHEV"]
                .groupby("year")["registrations"].sum()
            )
            for yr, share in (phev_by_yr / total_by_yr * 100).round(2).items():
                rows.append(_row("PHEV Observed (Eurostat)", yr, share,
                                 "actual", "PHEV", EUROSTAT_URL))
            logger.info("  Forecast: PHEV Observed — {} years", len(phev_by_yr))

            # ── 3. BEV+PHEV combined Observed (Eurostat) ─────────
            # Kept as a "total plug-in EV" reference line
            ev_by_yr = (
                df_eu[df_eu["powertrain"].isin(["BEV", "PHEV"])]
                .groupby("year")["registrations"].sum()
            )
            for yr, share in (ev_by_yr / total_by_yr * 100).round(2).items():
                rows.append(_row("EU Observed (Eurostat)", yr, share,
                                 "actual", "BEV+PHEV", EUROSTAT_URL))
            logger.info("  Forecast: EU BEV+PHEV Observed — {} years", len(ev_by_yr))
        else:
            logger.warning("  Forecast: no EU aggregate rows in registrations data")

    # ── Load IEA workbook once ───────────────────────────────────
    iea_path = _latest_bronze("iea_global_ev_data_*.xlsx")
    if iea_path is not None:
        try:
            df_iea = pd.read_excel(iea_path, sheet_name="GEVO_EV_2025")
            europe_cars = df_iea[
                (df_iea["region_country"] == "Europe")
                & (df_iea["mode"] == "Cars")
            ].copy()

            # ── 2. IEA Historical BEV+PHEV share ─────────────────
            hist_share = europe_cars[
                (europe_cars["parameter"] == "EV sales share")
                & (europe_cars["powertrain"] == "EV")
                & (europe_cars["category"] == "Historical")
            ].copy()
            hist_share = hist_share[hist_share["year"].between(2010, 2030)].sort_values("year")
            for _, r in hist_share.iterrows():
                rows.append(_row("IEA Historical (Europe)", r["year"], r["value"],
                                 "actual", "BEV+PHEV", IEA_URL))
            logger.info("  Forecast: IEA Historical BEV+PHEV — {} rows", len(hist_share))

            # ── 3. IEA STEPS BEV+PHEV — interpolate 2025–2029 ────
            steps_share = europe_cars[
                (europe_cars["parameter"] == "EV sales share")
                & (europe_cars["powertrain"] == "EV")
                & (europe_cars["category"] == "Projection-STEPS")
            ].copy()
            steps_share = steps_share[steps_share["year"].between(2024, 2030)].sort_values("year")
            if not steps_share.empty:
                anchors = steps_share.set_index("year")["value"]
                interpolated = _interpolate_anchors(anchors, 2024, 2030)
                for yr, val in interpolated.items():
                    rows.append(_row("IEA STEPS 2025", yr, val,
                                     "projection", "BEV+PHEV", IEA_URL))
                logger.info("  Forecast: IEA STEPS BEV+PHEV — {} rows (2024–2030)",
                            len(interpolated))

            # ── 5. PHEV STEPS — derive from PHEV/BEV sales ratio ─
            # Method: PHEV_share = EV_share × (PHEV_sales / (BEV_sales + PHEV_sales))
            # Uses IEA absolute sales numbers to split the EV share proportionally.
            ev_sales = europe_cars[
                (europe_cars["parameter"] == "EV sales")
                & (europe_cars["category"].isin(["Historical", "Projection-STEPS"]))
                & (europe_cars["powertrain"].isin(["BEV", "PHEV"]))
                & (europe_cars["year"].between(2024, 2030))
            ].copy()

            ev_share_all = europe_cars[
                (europe_cars["parameter"] == "EV sales share")
                & (europe_cars["powertrain"] == "EV")
                & (europe_cars["category"].isin(["Historical", "Projection-STEPS"]))
                & (europe_cars["year"].between(2024, 2030))
            ].copy()

            if not ev_sales.empty and not ev_share_all.empty:
                pivot = ev_sales.pivot_table(
                    index="year", columns="powertrain", values="value", aggfunc="last"
                )
                ev_share_idx = ev_share_all.drop_duplicates("year").set_index("year")["value"]
                total_plugin = pivot["BEV"] + pivot["PHEV"]

                # PHEV STEPS: PHEV fraction of total EV share
                phev_ratio = pivot["PHEV"] / total_plugin
                phev_share_anchors = (phev_ratio * ev_share_idx).dropna()
                if not phev_share_anchors.empty:
                    interpolated_phev = _interpolate_anchors(phev_share_anchors, 2024, 2030)
                    for yr, val in interpolated_phev.items():
                        rows.append(_row("PHEV STEPS 2025", yr, val,
                                         "projection", "PHEV", IEA_URL))
                    logger.info("  Forecast: PHEV STEPS — {} rows (2024–2030)",
                                len(interpolated_phev))

                # BEV STEPS: BEV fraction of total EV share
                bev_ratio = pivot["BEV"] / total_plugin
                bev_share_anchors = (bev_ratio * ev_share_idx).dropna()
                if not bev_share_anchors.empty:
                    interpolated_bev = _interpolate_anchors(bev_share_anchors, 2024, 2030)
                    for yr, val in interpolated_bev.items():
                        rows.append(_row("BEV STEPS 2025", yr, val,
                                         "projection", "BEV", IEA_URL))
                    logger.info("  Forecast: BEV STEPS — {} rows (2024–2030)",
                                len(interpolated_bev))

        except Exception as e:
            logger.error("Could not transform IEA forecast workbook {}: {}", iea_path.name, e)
    else:
        logger.warning("No IEA Global EV Data Explorer workbook found")

    # ── ACEA latest EU actual (BEV+PHEV) ────────────────────────
    acea = transform_acea_passenger_cars()
    if acea is not None and not acea.empty:
        eu_plugin = acea[acea["powertrain"].isin(["BEV", "PHEV"])]
        if not eu_plugin.empty:
            source_url = None
            if "source_url" in eu_plugin.columns and eu_plugin["source_url"].notna().any():
                source_url = eu_plugin["source_url"].dropna().iloc[0]
            rows.append(_row(
                "ACEA latest EU actual",
                int(eu_plugin["year"].max()),
                float(eu_plugin["share_pct"].sum()),
                "actual", "BEV+PHEV", source_url,
            ))

    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["source", "year", "ev_sales_share_pct", "series_type", "powertrain", "source_url"]
    )
    df.sort_values(["powertrain", "source", "year"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    logger.info("Forecast table built — {} rows, {} series, powertrains: {}",
                len(df),
                df["source"].nunique() if not df.empty else 0,
                df["powertrain"].unique().tolist() if not df.empty else [])
    return df


def run_silver() -> dict:
    logger.info("=" * 60)
    logger.info("SILVER LAYER — Clean & Transform")
    logger.info("=" * 60)

    # ── Source 1: Eurostat ───────────────────────────────────
    df_eurostat = transform_eurostat()

    # ── Source 2: OWID ───────────────────────────────────────
    df_owid = transform_owid()
    df_acea = transform_acea_passenger_cars()

    # ── Enforce: at least one real source must be available ─
    if df_eurostat is None and df_acea is None:
        raise DataUnavailableError(
            "No registration breakdown available from Eurostat or ACEA.\n"
            "Please run the pipeline with network access:\n"
            "  uv run python scripts/run_pipeline.py --layer bronze\n"
            "This will fetch live data from Eurostat, ACEA, OWID and IEA."
        )

    # ── Merge: Eurostat is primary ───────────────────────────
    if df_eurostat is not None:
        df_annual = df_eurostat.copy()

        # Cross-validate BEV share against OWID where available
        if df_owid is not None:
            _cross_validate_bev(df_annual, df_owid)
    else:
        # Eurostat unavailable; use the parsed official ACEA annual EU aggregate.
        logger.warning("Eurostat unavailable - using ACEA official annual EU aggregate.")
        df_annual = df_acea.copy()

    if df_acea is not None and not df_acea.empty:
        acea_years = set(df_acea["year"].astype(int).tolist())
        df_annual = df_annual[
            ~((df_annual["country_code"] == "EU") & (df_annual["year"].astype(int).isin(acea_years)))
        ].copy()
        df_annual = pd.concat([df_annual, df_acea], ignore_index=True)
        df_annual.sort_values(["country_code", "year", "powertrain"], inplace=True)

    # ── Save silver outputs ──────────────────────────────────
    results = {}

    annual_path = SILVER_DIR / "registrations_annual.parquet"
    df_annual.to_parquet(annual_path, index=False)
    logger.success("Saved → {} ({} rows)", annual_path.name, len(df_annual))
    results["annual"] = annual_path

    # Country-level slice (all countries, latest 5 years)
    df_countries = df_annual[df_annual["country_code"] != "EU"].copy()
    country_path = SILVER_DIR / "registrations_by_country.parquet"
    df_countries.to_parquet(country_path, index=False)
    logger.success("Saved → {} ({} rows)", country_path.name, len(df_countries))
    results["countries"] = country_path

    # OWID separately (for validation overlay)
    if df_owid is not None:
        owid_path = SILVER_DIR / "owid_ev_share.parquet"
        df_owid.to_parquet(owid_path, index=False)
        logger.success("Saved → {} ({} rows)", owid_path.name, len(df_owid))
        results["owid"] = owid_path

    # Forecast scenarios (pass df_annual so EU Observed is built without re-reading)
    df_forecast = build_forecast_df(df_annual=df_annual)
    forecast_path = SILVER_DIR / "forecast_scenarios.parquet"
    df_forecast.to_parquet(forecast_path, index=False)
    logger.success("Saved → {} ({} rows)", forecast_path.name, len(df_forecast))
    results["forecasts"] = forecast_path

    logger.info("=" * 60)
    logger.info("SILVER LAYER COMPLETE")
    logger.info("=" * 60)
    return results


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _cross_validate_bev(df_eurostat: pd.DataFrame, df_owid: pd.DataFrame) -> None:
    """
    Log a comparison between Eurostat BEV share and OWID EV (BEV+PHEV) share.
    Discrepancies > 10pp are flagged as warnings.
    """
    logger.info("Cross-validating BEV shares: Eurostat vs OWID …")
    bev  = df_eurostat[df_eurostat["powertrain"] == "BEV"][["country_code", "year", "share_pct"]].copy()
    phev = df_eurostat[df_eurostat["powertrain"] == "PHEV"][["country_code", "year", "share_pct"]].copy()

    plug_in = bev.merge(
        phev.rename(columns={"share_pct": "phev_share"}),
        on=["country_code", "year"], how="left"
    )
    plug_in["plug_in_share"] = plug_in["share_pct"] + plug_in["phev_share"].fillna(0)

    merged = plug_in.merge(
        df_owid.rename(columns={"ev_share_pct": "owid_share"}),
        on=["country_code", "year"], how="inner"
    )

    large_diffs = []
    for _, row in merged.iterrows():
        diff = abs(row["plug_in_share"] - row["owid_share"])
        if diff > 10:
            large_diffs.append((
                row["country_code"], int(row["year"]),
                row["plug_in_share"], row["owid_share"], diff
            ))

    if len(merged) > 0:
        avg_diff = abs(merged["plug_in_share"] - merged["owid_share"]).mean()
        logger.info("  Average BEV+PHEV share discrepancy: {:.2f}pp (Eurostat vs OWID)", avg_diff)
    if large_diffs:
        largest = sorted(large_diffs, key=lambda item: item[-1], reverse=True)[:5]
        logger.info(
            "  {} Eurostat/OWID country-year checks differ by >10pp; largest: {}",
            len(large_diffs),
            [
                f"{cc} {year}: {eurostat_share:.1f}% vs {owid_share:.1f}%"
                for cc, year, eurostat_share, owid_share, _ in largest
            ],
        )


if __name__ == "__main__":
    from config.logging_config import setup_logging
    from config.settings import LOG_DIR
    setup_logging(LOG_DIR)
    run_silver()
