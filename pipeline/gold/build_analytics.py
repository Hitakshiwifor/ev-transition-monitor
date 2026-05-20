"""
pipeline/gold/build_analytics.py
==================================
Gold layer — Produces dashboard-ready aggregated datasets from
the silver Parquet files.

Aggregations produced
─────────────────────
1. EU-total annual registrations by powertrain + shares  → eu_annual.parquet
2. Country-level BEV share (latest year available)       → country_bev_share.parquet
3. Market value estimates (registrations × avg price)    → market_value.parquet
4. Forecast scenario long-table                          → forecast_scenarios.parquet  (copy)
5. Summary KPI snapshot                                  → kpi_snapshot.json

Medallion role : GOLD — denormalised, optimised for direct chart consumption.
"""

import json
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import GOLD_DIR, SILVER_DIR

# ── Average new car price assumptions (EUR) ──────────────────
# Source-backed transaction-price anchors used for market-value estimation.
# Registration volumes come from Eurostat/ACEA; price anchors should be
# refreshed when the public DAT/JATO/ACEA source inputs are updated.
AVG_PRICE_BY_YEAR = {
    2020: 36_000,
    2021: 38_500,
    2022: 41_000,
    2023: 44_000,
    2024: 46_000,
    2025: 47_000,
}

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _load_silver(filename: str) -> pd.DataFrame | None:
    path = SILVER_DIR / filename
    if not path.exists():
        logger.warning("Silver file not found: {}", filename)
        return None
    df = pd.read_parquet(path)
    logger.debug("Loaded {} — {} rows", filename, len(df))
    return df


def _interp_price(year: int) -> float:
    years = sorted(AVG_PRICE_BY_YEAR)
    if year <= years[0]:
        return AVG_PRICE_BY_YEAR[years[0]]
    if year >= years[-1]:
        return AVG_PRICE_BY_YEAR[years[-1]]
    lo = max(y for y in years if y <= year)
    hi = min(y for y in years if y >= year)
    if lo == hi:
        return AVG_PRICE_BY_YEAR[lo]
    t = (year - lo) / (hi - lo)
    return AVG_PRICE_BY_YEAR[lo] + t * (AVG_PRICE_BY_YEAR[hi] - AVG_PRICE_BY_YEAR[lo])


# ─────────────────────────────────────────────────────────────
# Gold aggregations
# ─────────────────────────────────────────────────────────────

def build_eu_annual(df_annual: pd.DataFrame) -> pd.DataFrame:
    """
    EU-level total registrations per year × powertrain,
    with share % and market value estimate.
    """
    # Use EU aggregate if present, else sum all countries
    if "EU" in df_annual["country_code"].values:
        df = df_annual[df_annual["country_code"] == "EU"].copy()
    else:
        df = df_annual.groupby(
            ["year", "powertrain"], as_index=False
        )["registrations"].sum()
        totals = df.groupby("year")["registrations"].transform("sum")
        df["share_pct"] = (df["registrations"] / totals * 100).round(2)

    df["avg_price_eur"] = df["year"].apply(lambda y: round(_interp_price(int(y))))
    df["market_value_eur_bn"] = (
        df["registrations"] * df["avg_price_eur"] / 1e9
    ).round(2)

    # Year-over-year change in registrations
    df.sort_values(["powertrain", "year"], inplace=True)
    df["yoy_change_pct"] = df.groupby("powertrain")["registrations"].pct_change() * 100
    df["yoy_change_pct"] = df["yoy_change_pct"].round(1)

    logger.success("EU annual gold — {} rows", len(df))
    return df


ISO2_TO_ISO3 = {
    "AT":"AUT","BE":"BEL","BG":"BGR","CY":"CYP","CZ":"CZE",
    "DE":"DEU","DK":"DNK","EE":"EST","EL":"GRC","ES":"ESP",
    "FI":"FIN","FR":"FRA","HR":"HRV","HU":"HUN","IE":"IRL",
    "IT":"ITA","LT":"LTU","LU":"LUX","LV":"LVA","MT":"MLT",
    "NL":"NLD","PL":"POL","PT":"PRT","RO":"ROU","SE":"SWE",
    "SI":"SVN","SK":"SVK","NO":"NOR","IS":"ISL","CH":"CHE",
    "UK":"GBR","GB":"GBR","LI":"LIE",
}


def build_country_bev_share(df_annual: pd.DataFrame) -> pd.DataFrame:
    """
    Latest-year BEV share per country for choropleth map (backward compat).
    """
    df = df_annual[df_annual["country_code"] != "EU"].copy()
    latest_year = int(df["year"].max())
    df = df[df["year"] == latest_year].copy()

    bev = df[df["powertrain"] == "BEV"][["country_code", "country_name", "registrations", "share_pct"]].copy()
    bev.rename(columns={"registrations": "bev_registrations", "share_pct": "bev_share_pct"}, inplace=True)

    total = df.groupby(["country_code", "country_name"])["registrations"].sum().reset_index()
    total.rename(columns={"registrations": "total_registrations"}, inplace=True)

    merged = total.merge(bev, on=["country_code", "country_name"], how="left")
    merged["bev_share_pct"]      = merged["bev_share_pct"].fillna(0)
    merged["bev_registrations"]  = merged["bev_registrations"].fillna(0).astype(int)
    merged["year"]               = latest_year
    merged["iso3"]               = merged["country_code"].map(ISO2_TO_ISO3)

    logger.success("Country BEV share gold — {} rows (year={})", len(merged), latest_year)
    return merged


def build_country_powertrain_annual(df_annual: pd.DataFrame) -> pd.DataFrame:
    """
    Full powertrain breakdown for every country × year × powertrain.
    All powertrains (BEV, PHEV, HEV, ICE_Petrol, ICE_Diesel, Other).
    Used by the map (year slider), country comparison, and trend charts.
    """
    df = df_annual[df_annual["country_code"] != "EU"].copy()
    df["iso3"] = df["country_code"].map(ISO2_TO_ISO3)

    # Ensure share_pct is recomputed cleanly per country × year
    totals = df.groupby(["country_code", "year"])["registrations"].transform("sum")
    df["share_pct"] = (df["registrations"] / totals * 100).round(2)

    df.sort_values(["country_code", "year", "powertrain"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    logger.success("Country powertrain annual gold — {} rows, {} countries, {} years",
                   len(df), df["country_code"].nunique(), df["year"].nunique())
    return df


def build_market_value_summary(df_annual: pd.DataFrame) -> pd.DataFrame:
    """
    Total EU market value (EUR billions) per year, with low/high band.
    """
    if "EU" in df_annual["country_code"].values:
        df = df_annual[df_annual["country_code"] == "EU"].copy()
    else:
        df = df_annual.groupby(["year"], as_index=False)["registrations"].sum()

    total_regs = df.groupby("year")["registrations"].sum().reset_index()
    total_regs.rename(columns={"registrations": "total_registrations"}, inplace=True)

    total_regs["avg_price_eur"] = total_regs["year"].apply(lambda y: round(_interp_price(int(y))))
    total_regs["market_value_eur_bn"]     = (total_regs["total_registrations"] * total_regs["avg_price_eur"] / 1e9).round(1)
    total_regs["market_value_low_eur_bn"] = (total_regs["total_registrations"] * (total_regs["avg_price_eur"] * 0.85) / 1e9).round(1)
    total_regs["market_value_high_eur_bn"]= (total_regs["total_registrations"] * (total_regs["avg_price_eur"] * 1.15) / 1e9).round(1)

    logger.success("Market value gold — {} years", len(total_regs))
    return total_regs


def build_kpi_snapshot(df_annual: pd.DataFrame, df_forecast: pd.DataFrame) -> dict:
    """
    JSON snapshot of key metrics for the KPI cards on the dashboard.
    """
    latest_year = int(df_annual["year"].max())
    df_latest = df_annual[df_annual["year"] == latest_year].copy()

    # EU aggregate
    if "EU" in df_latest["country_code"].values:
        df_eu = df_latest[df_latest["country_code"] == "EU"]
    else:
        df_eu = df_latest

    def _share(pt):
        regs = int(df_eu[df_eu["powertrain"] == pt]["registrations"].sum())
        return round(regs / total_regs * 100, 1) if total_regs else 0.0, regs

    total_regs          = int(df_eu["registrations"].sum())
    bev_share,  bev_regs  = _share("BEV")
    phev_share, phev_regs = _share("PHEV")
    hev_share,  hev_regs  = _share("HEV")
    ice_p_share, ice_p_regs = _share("ICE_Petrol")
    ice_d_share, ice_d_regs = _share("ICE_Diesel")
    other_share, _       = _share("Other")
    ice_share            = round(ice_p_share + ice_d_share, 1)
    electrified_share    = round(bev_share + phev_share + hev_share, 1)

    avg_price    = round(_interp_price(latest_year))
    market_value = round(total_regs * avg_price / 1e9, 1)

    # YoY change vs prior year
    prior_year = latest_year - 1
    df_prior = df_annual[df_annual["year"] == prior_year]
    if "EU" in df_prior["country_code"].values:
        df_prior = df_prior[df_prior["country_code"] == "EU"]
    prior_total = int(df_prior["registrations"].sum()) if not df_prior.empty else total_regs
    yoy_pct     = round((total_regs - prior_total) / prior_total * 100, 1) if prior_total else 0

    def _prior_share(pt):
        if df_prior.empty or prior_total == 0:
            return 0.0
        r = int(df_prior[df_prior["powertrain"] == pt]["registrations"].sum())
        return round(r / prior_total * 100, 1)

    bev_share_delta  = round(bev_share  - _prior_share("BEV"),  1)
    phev_share_delta = round(phev_share - _prior_share("PHEV"), 1)
    hev_share_delta  = round(hev_share  - _prior_share("HEV"),  1)
    ice_share_delta  = round(ice_share  - (_prior_share("ICE_Petrol") + _prior_share("ICE_Diesel")), 1)

    snapshot = {
        "reference_year":            latest_year,
        "total_registrations":       total_regs,
        "total_registrations_fmt":   f"{total_regs/1e6:.2f}M",
        "yoy_change_pct":            yoy_pct,
        # BEV
        "bev_registrations":         bev_regs,
        "bev_share_pct":             bev_share,
        "bev_share_delta_pp":        bev_share_delta,
        # PHEV
        "phev_registrations":        phev_regs,
        "phev_share_pct":            phev_share,
        "phev_share_delta_pp":       phev_share_delta,
        # HEV
        "hev_registrations":         hev_regs,
        "hev_share_pct":             hev_share,
        "hev_share_delta_pp":        hev_share_delta,
        # ICE combined
        "ice_share_pct":             ice_share,
        "ice_share_delta_pp":        ice_share_delta,
        # ICE split
        "ice_petrol_registrations":  ice_p_regs,
        "ice_petrol_share_pct":      ice_p_share,
        "ice_diesel_registrations":  ice_d_regs,
        "ice_diesel_share_pct":      ice_d_share,
        # Other
        "other_share_pct":           other_share,
        # Electrified (BEV+PHEV+HEV)
        "electrified_share_pct":     electrified_share,
        # Market
        "market_value_eur_bn":       market_value,
        "avg_price_eur":             avg_price,
        "generated_at":              pd.Timestamp.utcnow().isoformat(),
    }

    logger.success("KPI snapshot built for year {}", latest_year)
    return snapshot


# ─────────────────────────────────────────────────────────────
# Run all gold steps
# ─────────────────────────────────────────────────────────────

def run_gold() -> dict:
    logger.info("=== GOLD LAYER START ===")

    df_annual = _load_silver("registrations_annual.parquet")
    if df_annual is None:
        logger.error("Cannot run gold — annual silver file missing")
        return {}

    df_forecast = _load_silver("forecast_scenarios.parquet")

    # 1. EU annual
    df_eu = build_eu_annual(df_annual)
    p = GOLD_DIR / "eu_annual.parquet"
    df_eu.to_parquet(p, index=False)
    logger.info("Saved → {}", p.name)

    # 2. Country BEV share (latest year — backward compat for map)
    df_map = build_country_bev_share(df_annual)
    p = GOLD_DIR / "country_bev_share.parquet"
    df_map.to_parquet(p, index=False)
    logger.info("Saved → {}", p.name)

    # 2b. Full country × year × powertrain breakdown (all powertrains)
    df_ctry_pt = build_country_powertrain_annual(df_annual)
    p = GOLD_DIR / "country_powertrain_annual.parquet"
    df_ctry_pt.to_parquet(p, index=False)
    logger.info("Saved → {}", p.name)

    # 3. Market value
    df_mv = build_market_value_summary(df_annual)
    p = GOLD_DIR / "market_value.parquet"
    df_mv.to_parquet(p, index=False)
    logger.info("Saved → {}", p.name)

    # 4. Forecast (copy from silver)
    if df_forecast is not None:
        p = GOLD_DIR / "forecast_scenarios.parquet"
        df_forecast.to_parquet(p, index=False)
        logger.info("Saved → {}", p.name)

    # 5. KPI snapshot
    kpi = build_kpi_snapshot(df_annual, df_forecast)
    p = GOLD_DIR / "kpi_snapshot.json"
    with open(p, "w") as fh:
        json.dump(kpi, fh, indent=2)
    logger.info("Saved → {}", p.name)

    logger.info("=== GOLD LAYER COMPLETE ===")
    return kpi


if __name__ == "__main__":
    from config.logging_config import setup_logging
    from config.settings import LOG_DIR
    setup_logging(LOG_DIR)
    run_gold()
