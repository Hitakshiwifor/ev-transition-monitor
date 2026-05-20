"""
Dash callbacks for the EV Transition Monitor dashboard.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, dcc, no_update

from dashboard.analytics import (
    ALL_COUNTRIES,
    DEFAULT_POWERTRAINS,
    DEFAULT_SCOPE,
    aggregate_powertrain,
    available_actual_years,
    country_snapshot,
    kpi_summary,
    market_value_series,
    normalize_year_range,
    selection_label,
)
from dashboard.components.country_ranking import build_country_ranking_table
from dashboard.components.forecast import build_forecast_chart
from dashboard.components.kpi_cards import build_kpi_cards
from dashboard.components.map_view import build_map_chart
from dashboard.components.market_mix import build_market_mix_chart
from dashboard.components.market_value import build_market_value_chart
from dashboard.components.powertrain import build_powertrain_chart
from dashboard.components.share_change import build_share_change_chart
from dashboard.data_loader import load_all

_CHART_H_PRIMARY = 155
_CHART_H_BOTTOM  = 155


def _defaults() -> tuple[int, int, str, str]:
    data = load_all()
    years = available_actual_years(data)
    year_from, year_to = normalize_year_range(2015, years[-1] if years else 2024, years)
    return year_from, year_to, ALL_COUNTRIES, DEFAULT_SCOPE


def register_callbacks(app) -> None:

    @app.callback(
        Output("filter-year-from", "value"),
        Output("filter-year-to", "value"),
        Output("filter-country", "value"),
        Input("reset-filters", "n_clicks"),
        prevent_initial_call=True,
    )
    def reset_filters(_n_clicks):
        year_from, year_to, country, _scope = _defaults()
        return year_from, year_to, country

    @app.callback(
        Output("filter-scope", "data"),
        Input("scope-eu27", "n_clicks"),
        Input("scope-major", "n_clicks"),
        Input("scope-europe", "n_clicks"),
        Input("reset-filters", "n_clicks"),
        State("filter-scope", "data"),
        prevent_initial_call=True,
    )
    def update_scope_store(_eu27, _major, _europe, _reset, current_scope):
        trigger = ctx.triggered_id
        if trigger == "scope-major":
            return "MAJOR"
        if trigger == "scope-europe":
            return "EUROPE"
        if trigger in {"scope-eu27", "reset-filters"}:
            return DEFAULT_SCOPE
        return current_scope or DEFAULT_SCOPE

    @app.callback(
        Output("scope-eu27", "className"),
        Output("scope-major", "className"),
        Output("scope-europe", "className"),
        Input("filter-scope", "data"),
        prevent_initial_call=False,
    )
    def update_scope_classes(scope):
        scope = scope or DEFAULT_SCOPE
        return (
            f"segmented-button{' active' if scope == 'EU27' else ''}",
            f"segmented-button{' active' if scope == 'MAJOR' else ''}",
            f"segmented-button{' active' if scope == 'EUROPE' else ''}",
        )

    @app.callback(
        Output("kpi-cards-container", "children"),
        Output("chart-powertrain-trend", "figure"),
        Output("chart-market-mix", "figure"),
        Output("chart-share-change", "figure"),
        Output("chart-map", "figure"),
        Output("country-ranking-table", "children"),
        Output("chart-market-value", "figure"),
        Output("chart-forecast", "figure"),
        Output("title-powertrain-trend", "children"),
        Output("title-market-mix", "children"),
        Output("subtitle-market-mix", "children"),
        Output("title-country-map", "children"),
        Output("title-country-ranking", "children"),
        Output("title-share-change", "children"),
        Input("filter-year-from", "value"),
        Input("filter-year-to", "value"),
        Input("filter-country", "value"),
        Input("filter-scope", "data"),
        prevent_initial_call=False,
    )
    def update_dashboard(year_from, year_to, country, scope):
        data = load_all()
        years = available_actual_years(data)
        start, end = normalize_year_range(year_from, year_to, years)
        scope = scope or DEFAULT_SCOPE
        country = country or ALL_COUNTRIES

        agg = aggregate_powertrain(data, scope, country)
        summary = kpi_summary(agg, end)
        selected = selection_label(scope, country, data.get("country_powertrain_annual"))
        countries_for_year = country_snapshot(data, scope, end)
        value_df = market_value_series(agg, data.get("market_value"))

        actual_year = summary["year"]

        return (
            build_kpi_cards(summary),
            build_powertrain_chart(agg, DEFAULT_POWERTRAINS, start, end, chart_type="volume"),
            build_market_mix_chart(summary),
            build_share_change_chart(summary),
            build_map_chart(countries_for_year, "electrified_share_pct"),
            build_country_ranking_table(countries_for_year, metric="electrified_share_pct", count=10),
            build_market_value_chart(value_df, start, end),
            build_forecast_chart(data.get("forecast"), year_from=start),
            f"Vehicle Registrations by Powertrain ({start}-{end})",
            f"Current Market Mix ({actual_year})",
            selected.short,
            f"Electrified Vehicle Adoption by Country ({actual_year})",
            f"Top 10 vs Bottom 10 Countries by Electrified Share ({actual_year})",
            f"Powertrain Share Change ({actual_year - 1} → {actual_year})",
        )

    @app.callback(
        Output("panel-data-download", "data"),
        Input({"type": "download-csv-btn", "panel": ALL}, "n_clicks"),
        State("filter-year-from", "value"),
        State("filter-year-to", "value"),
        State("filter-country", "value"),
        State("filter-scope", "data"),
        prevent_initial_call=True,
    )
    def download_panel_data(n_clicks_list, year_from, year_to, country, scope):
        if not any(n for n in (n_clicks_list or []) if n):
            return no_update
        trigger = ctx.triggered_id
        if not trigger:
            return no_update

        panel_id = trigger["panel"]
        data = load_all()
        years = available_actual_years(data)
        start, end = normalize_year_range(year_from, year_to, years)
        resolved_scope = scope or DEFAULT_SCOPE
        resolved_country = country or ALL_COUNTRIES

        if panel_id in {"powertrain-trend", "market-mix", "share-change"}:
            agg = aggregate_powertrain(data, resolved_scope, resolved_country)
            df = agg[(agg["year"] >= start) & (agg["year"] <= end)].copy()
            filename = f"ev_registrations_{start}_{end}.csv"

        elif panel_id in {"country-map", "country-ranking"}:
            df = country_snapshot(data, resolved_scope, end)
            filename = f"ev_country_snapshot_{end}.csv"

        elif panel_id == "market-value":
            agg = aggregate_powertrain(data, resolved_scope, resolved_country)
            df = market_value_series(agg, data.get("market_value"))
            df = df[(df["year"] >= start) & (df["year"] <= end)].copy()
            filename = f"ev_market_value_{start}_{end}.csv"

        elif panel_id == "forecast":
            df = data.get("forecast")
            filename = "ev_forecast_scenarios.csv"

        else:
            return no_update

        if df is None or (hasattr(df, "empty") and df.empty):
            return no_update

        return dcc.send_data_frame(df.to_csv, filename, index=False)
