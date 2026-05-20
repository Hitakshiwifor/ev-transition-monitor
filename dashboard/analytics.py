"""
Shared dashboard analytics helpers.

These functions keep UI callbacks focused on layout work while all filtering,
aggregation, KPI calculations, and country snapshots stay in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from config.settings import EU_COUNTRIES

ALL_COUNTRIES = "__ALL__"
DEFAULT_SCOPE = "EU27"
DEFAULT_POWERTRAINS = ["BEV", "PHEV", "HEV", "ICE_Petrol", "ICE_Diesel"]

POWERTRAIN_ORDER = ["BEV", "PHEV", "HEV", "ICE_Petrol", "ICE_Diesel", "Other"]
DISPLAY_POWERTRAINS = ["BEV", "PHEV", "HEV", "ICE_Petrol", "ICE_Diesel"]

POWERTRAIN_LABELS = {
    "BEV": "BEV",
    "PHEV": "PHEV",
    "HEV": "HEV",
    "ICE_Petrol": "Petrol",
    "ICE_Diesel": "Diesel",
    "Other": "Other",
    "TOTAL": "Total Market",
}

POWERTRAIN_COLORS = {
    "BEV": "#0aa15f",
    "PHEV": "#8b45d9",
    "HEV": "#ff9700",
    "ICE_Petrol": "#2f7df6",
    "ICE_Diesel": "#5f6b82",
    "Other": "#9aa6b2",
    "TOTAL": "#071437",
}

EU27_CODES = set(EU_COUNTRIES) - {"NO", "IS", "CH", "UK"}
MAJOR_MARKET_CODES = {"DE", "FR", "IT", "ES", "UK"}


@dataclass(frozen=True)
class SelectionLabel:
    title: str
    short: str


def selection_label(scope: str, country: str | None, country_df: pd.DataFrame | None) -> SelectionLabel:
    if country and country != ALL_COUNTRIES and country_df is not None and not country_df.empty:
        match = country_df[country_df["country_code"] == country]
        if not match.empty:
            name = str(match["country_name"].iloc[0])
            return SelectionLabel(name, name)

    if scope == "MAJOR":
        return SelectionLabel("Major European markets", "Major Markets")
    if scope == "EUROPE":
        return SelectionLabel("All available European countries", "All Europe")
    return SelectionLabel("European Union (EU-27)", "EU27")


def available_actual_years(data: dict) -> list[int]:
    frames = [
        data.get("eu_annual"),
        data.get("country_powertrain_annual"),
    ]
    years: set[int] = set()
    for df in frames:
        if df is not None and not df.empty and "year" in df.columns:
            years.update(int(y) for y in df["year"].dropna().unique())
    return sorted(years)


def country_options(data: dict) -> list[dict]:
    df = data.get("country_powertrain_annual")
    count = 0
    options = []
    if df is not None and not df.empty:
        countries = (
            df[["country_code", "country_name"]]
            .drop_duplicates()
            .sort_values("country_name")
        )
        count = len(countries)
        options = [
            {"label": row.country_name, "value": row.country_code}
            for row in countries.itertuples(index=False)
        ]
    return [{"label": f"All Countries ({count})", "value": ALL_COUNTRIES}] + options


def resolve_year(df: pd.DataFrame | None, requested_year: int | None) -> int | None:
    if df is None or df.empty or "year" not in df.columns:
        return requested_year
    years = sorted(int(y) for y in df["year"].dropna().unique())
    if not years:
        return requested_year
    if requested_year is None:
        return years[-1]
    candidates = [year for year in years if year <= requested_year]
    return candidates[-1] if candidates else years[0]


def normalize_year_range(year_from: int | None, year_to: int | None, fallback_years: list[int]) -> tuple[int, int]:
    if not fallback_years:
        return int(year_from or 2015), int(year_to or 2024)
    start = int(year_from or fallback_years[0])
    end = int(year_to or fallback_years[-1])
    if start > end:
        start, end = end, start
    return start, end


def _scope_filter(df: pd.DataFrame, scope: str) -> pd.DataFrame:
    if scope == "MAJOR":
        return df[df["country_code"].isin(MAJOR_MARKET_CODES)]
    if scope == "EUROPE":
        return df
    return df[df["country_code"].isin(EU27_CODES)]


def _aggregate_from_country_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["year", "powertrain", "registrations", "share_pct"])

    grouped = (
        df.groupby(["year", "powertrain"], observed=True, as_index=False)["registrations"]
        .sum()
        .sort_values(["year", "powertrain"])
    )
    totals = grouped.groupby("year", as_index=False)["registrations"].sum()
    totals = totals.rename(columns={"registrations": "total_registrations"})
    grouped = grouped.merge(totals, on="year", how="left")
    grouped["share_pct"] = grouped["registrations"] / grouped["total_registrations"] * 100
    return grouped


def aggregate_powertrain(data: dict, scope: str, country: str | None) -> pd.DataFrame:
    country_df = data.get("country_powertrain_annual")
    eu_df = data.get("eu_annual")

    if country and country != ALL_COUNTRIES and country_df is not None and not country_df.empty:
        filtered = country_df[country_df["country_code"] == country]
        return _aggregate_from_country_df(filtered)

    if scope == "EU27" and eu_df is not None and not eu_df.empty:
        df = eu_df.copy()
        df["total_registrations"] = df.groupby("year")["registrations"].transform("sum")
        return df[["year", "powertrain", "registrations", "share_pct", "total_registrations"]]

    if country_df is None or country_df.empty:
        return pd.DataFrame(columns=["year", "powertrain", "registrations", "share_pct"])

    return _aggregate_from_country_df(_scope_filter(country_df, scope))


def country_snapshot(data: dict, scope: str, year_to: int | None) -> pd.DataFrame:
    country_df = data.get("country_powertrain_annual")
    if country_df is None or country_df.empty:
        return pd.DataFrame()

    filtered = _scope_filter(country_df, scope)
    year = resolve_year(filtered, year_to)
    if year is None:
        return pd.DataFrame()
    filtered = filtered[filtered["year"] == year]
    if filtered.empty:
        return pd.DataFrame()

    pivot = (
        filtered.pivot_table(
            index=["country_code", "country_name", "iso3", "year"],
            columns="powertrain",
            values="registrations",
            aggfunc="sum",
            fill_value=0,
            observed=True,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    for col in POWERTRAIN_ORDER:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot["total_registrations"] = pivot[POWERTRAIN_ORDER].sum(axis=1)
    pivot["bev_registrations"] = pivot["BEV"]
    pivot["phev_registrations"] = pivot["PHEV"]
    pivot["hev_registrations"] = pivot["HEV"]
    pivot["electrified_registrations"] = pivot[["BEV", "PHEV", "HEV"]].sum(axis=1)

    def share(col: str) -> pd.Series:
        return (pivot[col] / pivot["total_registrations"] * 100).fillna(0)

    pivot["bev_share_pct"] = share("BEV")
    pivot["phev_share_pct"] = share("PHEV")
    pivot["hev_share_pct"] = share("HEV")
    pivot["electrified_share_pct"] = (
        pivot["electrified_registrations"] / pivot["total_registrations"] * 100
    ).fillna(0)
    pivot["ice_share_pct"] = (
        (pivot["ICE_Petrol"] + pivot["ICE_Diesel"]) / pivot["total_registrations"] * 100
    ).fillna(0)
    return pivot.sort_values("country_name")


def kpi_summary(agg: pd.DataFrame, year_to: int | None) -> dict:
    if agg is None or agg.empty:
        return {
            "year": year_to or 2024,
            "previous_year": None,
            "total_registrations": 0,
            "total_delta_pct": 0,
            "shares": {},
            "share_deltas": {},
            "registrations": {},
        }

    year = resolve_year(agg, year_to)
    current = agg[agg["year"] == year].copy()
    years = sorted(int(y) for y in agg["year"].dropna().unique() if int(y) < int(year))
    previous_year = years[-1] if years else None
    previous = agg[agg["year"] == previous_year].copy() if previous_year else pd.DataFrame()

    total = float(current["registrations"].sum())
    previous_total = float(previous["registrations"].sum()) if not previous.empty else 0
    total_delta = ((total - previous_total) / previous_total * 100) if previous_total else 0

    current_by_pt = current.set_index("powertrain")
    previous_by_pt = previous.set_index("powertrain") if not previous.empty else pd.DataFrame()

    shares = {}
    deltas = {}
    regs = {}
    for pt in POWERTRAIN_ORDER:
        share = float(current_by_pt["share_pct"].get(pt, 0)) if not current_by_pt.empty else 0
        prev_share = (
            float(previous_by_pt["share_pct"].get(pt, 0))
            if not previous_by_pt.empty and "share_pct" in previous_by_pt
            else 0
        )
        registrations = (
            float(current_by_pt["registrations"].get(pt, 0)) if not current_by_pt.empty else 0
        )
        shares[pt] = share
        deltas[pt] = share - prev_share
        regs[pt] = registrations

    electrified_share = shares["BEV"] + shares["PHEV"] + shares["HEV"]
    previous_electrified_share = 0
    if not previous.empty:
        previous_electrified_share = float(
            previous[previous["powertrain"].isin(["BEV", "PHEV", "HEV"])]["share_pct"].sum()
        )
    shares["Electrified"] = electrified_share
    deltas["Electrified"] = electrified_share - previous_electrified_share
    regs["Electrified"] = regs["BEV"] + regs["PHEV"] + regs["HEV"]

    shares["ICE"] = shares["ICE_Petrol"] + shares["ICE_Diesel"]
    deltas["ICE"] = deltas["ICE_Petrol"] + deltas["ICE_Diesel"]
    regs["ICE"] = regs["ICE_Petrol"] + regs["ICE_Diesel"]

    return {
        "year": int(year),
        "previous_year": int(previous_year) if previous_year else None,
        "total_registrations": total,
        "total_delta_pct": total_delta,
        "shares": shares,
        "share_deltas": deltas,
        "registrations": regs,
    }


def market_value_series(agg: pd.DataFrame, market_value_df: pd.DataFrame | None) -> pd.DataFrame:
    if agg is None or agg.empty:
        return pd.DataFrame()

    totals = agg.groupby("year", as_index=False)["registrations"].sum()
    totals = totals.rename(columns={"registrations": "total_registrations"})

    if market_value_df is not None and not market_value_df.empty:
        price = market_value_df[["year", "avg_price_eur"]].drop_duplicates()
        totals = totals.merge(price, on="year", how="left")
    else:
        totals["avg_price_eur"] = 46000

    totals["avg_price_eur"] = totals["avg_price_eur"].ffill().bfill().fillna(46000)
    totals["market_value_eur_bn"] = totals["total_registrations"] * totals["avg_price_eur"] / 1e9
    totals["market_value_low_eur_bn"] = totals["market_value_eur_bn"] * 0.85
    totals["market_value_high_eur_bn"] = totals["market_value_eur_bn"] * 1.15
    return totals


def format_millions(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.0f}K"
    return f"{value:.0f}"


def format_delta(value: float, suffix: str = "pp") -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f} {suffix}"


def format_generated_at(value: str | None) -> str:
    if not value:
        return "Last updated: not available"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return f"Last updated: {value}"
    return f"Last updated: {parsed.strftime('%d %b %Y')}"
