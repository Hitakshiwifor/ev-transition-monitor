"""
Single-screen layout for the European EV Transition Monitor.
No-scroll design: all panels fit within 100vh.
"""

from __future__ import annotations

from dash import dcc, html

from dashboard.analytics import (
    ALL_COUNTRIES,
    DEFAULT_POWERTRAINS,
    DEFAULT_SCOPE,
    aggregate_powertrain,
    available_actual_years,
    country_options,
    country_snapshot,
    format_generated_at,
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

_CHART_H_PRIMARY  = 155
_CHART_H_MAP      = 170
_CHART_H_BOTTOM   = 155


def _year_options(years: list[int]) -> list[dict]:
    return [{"label": str(year), "value": year} for year in years]


def _graph(graph_id: str, figure, height: int = 160) -> dcc.Graph:
    return dcc.Graph(
        id=graph_id,
        figure=figure,
        config={"displayModeBar": False, "scrollZoom": False, "responsive": True},
        style={"minHeight": "0", "flex": "1 1 0"},
        className="dashboard-graph",
    )


def _panel(
    title: str,
    subtitle: str,
    children,
    class_name: str = "",
    title_id: str | None = None,
    subtitle_id: str | None = None,
    panel_id: str | None = None,
) -> html.Section:
    body = children if isinstance(children, list) else [children]
    title_props = {"className": "panel-title"}
    subtitle_props = {"className": "panel-subtitle"}
    if title_id:
        title_props["id"] = title_id
    if subtitle_id:
        subtitle_props["id"] = subtitle_id

    if panel_id:
        menu = html.Details(
            className="panel-menu-wrapper",
            children=[
                html.Summary("⋯", className="panel-menu"),
                html.Div(
                    className="panel-menu-dropdown",
                    children=[
                        html.Button(
                            "Download CSV",
                            id={"type": "download-csv-btn", "panel": panel_id},
                            className="panel-menu-item",
                            n_clicks=0,
                        ),
                    ],
                ),
            ],
        )
    else:
        menu = html.Button("⋯", className="panel-menu", type="button")

    return html.Section(
        className=f"panel {class_name}".strip(),
        children=[
            html.Div(
                className="panel-header",
                children=[
                    html.Div(
                        children=[
                            html.H2(title, **title_props),
                            html.P(subtitle, **subtitle_props),
                        ]
                    ),
                    menu,
                ],
            ),
            *body,
        ],
    )


def _filter_bar(years: list[int], countries: list[dict]) -> html.Div:
    default_from, default_to = normalize_year_range(2015, years[-1] if years else 2024, years)

    def scope_button(button_id: str, label: str, value: str) -> html.Button:
        active = value == DEFAULT_SCOPE
        return html.Button(
            label,
            id=button_id,
            className=f"segmented-button{' active' if active else ''}",
            type="button",
        )

    return html.Div(
        className="filter-panel",
        children=[
            dcc.Store(id="filter-scope", data=DEFAULT_SCOPE),
            html.Div(
                className="filter-field filter-field--years",
                children=[
                    html.Label("Year range", className="filter-label"),
                    html.Div(
                        className="year-range-control",
                        children=[
                            dcc.Dropdown(
                                id="filter-year-from",
                                options=_year_options(years),
                                value=default_from,
                                clearable=False,
                                searchable=False,
                                className="compact-dropdown",
                            ),
                            html.Span("-", className="year-separator"),
                            dcc.Dropdown(
                                id="filter-year-to",
                                options=_year_options(years),
                                value=default_to,
                                clearable=False,
                                searchable=False,
                                className="compact-dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="filter-field filter-field--country",
                children=[
                    html.Label("Country / Region", className="filter-label"),
                    dcc.Dropdown(
                        id="filter-country",
                        options=countries,
                        value=ALL_COUNTRIES,
                        clearable=False,
                        className="control-dropdown",
                    ),
                ],
            ),
            html.Div(
                className="filter-field filter-field--scope",
                children=[
                    html.Label("Market scope", className="filter-label"),
                    html.Div(
                        className="segmented-control",
                        children=[
                            scope_button("scope-eu27", "EU27", "EU27"),
                            scope_button("scope-major", "Major Markets", "MAJOR"),
                            scope_button("scope-europe", "All Europe", "EUROPE"),
                        ],
                    ),
                ],
            ),
            html.Button("Reset", id="reset-filters", className="reset-button", type="button"),
        ],
    )


def _header(last_updated: str) -> html.Header:
    return html.Header(
        className="topbar",
        children=[
            html.Div(
                className="brand-area",
                children=[
                    html.Div("EV", className="brand-mark"),
                    html.Div(
                        children=[
                            html.H1("European EV Transition Monitor", className="app-title"),
                            html.P(
                                "Tracking Europe's shift from ICE to electric and hybrid mobility",
                                className="app-subtitle",
                            ),
                        ]
                    ),
                ],
            ),
            html.Span(last_updated, className="topbar-updated"),
        ],
    )



def build_layout() -> html.Div:
    data = load_all()
    years = available_actual_years(data)
    if not years:
        years = list(range(2015, 2025))
    year_from, year_to = normalize_year_range(2015, years[-1], years)
    countries = country_options(data)

    agg = aggregate_powertrain(data, DEFAULT_SCOPE, ALL_COUNTRIES)
    summary = kpi_summary(agg, year_to)
    selected = selection_label(DEFAULT_SCOPE, ALL_COUNTRIES, data.get("country_powertrain_annual"))
    countries_for_year = country_snapshot(data, DEFAULT_SCOPE, year_to)
    value_df = market_value_series(agg, data.get("market_value"))
    last_updated = format_generated_at(data.get("kpi", {}).get("generated_at"))

    return html.Div(
        className="dashboard-shell",
        children=[
            dcc.Download(id="panel-data-download"),
            _header(last_updated),
            _filter_bar(years, countries),
            html.Main(
                className="dashboard-main",
                children=[
                    html.Div(id="kpi-cards-container", children=build_kpi_cards(summary)),
                    html.Div(
                        className="grid grid--primary",
                        children=[
                            _panel(
                                f"Vehicle Registrations by Powertrain ({year_from}-{year_to})",
                                "Annual registrations by powertrain type",
                                _graph(
                                    "chart-powertrain-trend",
                                    build_powertrain_chart(
                                        agg, DEFAULT_POWERTRAINS, year_from, year_to,
                                        chart_type="volume", height=_CHART_H_PRIMARY,
                                    ),
                                    _CHART_H_PRIMARY,
                                ),
                                "panel--trend",
                                title_id="title-powertrain-trend",
                                panel_id="powertrain-trend",
                            ),
                            _panel(
                                f"Current Market Mix ({summary['year']})",
                                selected.short,
                                _graph(
                                    "chart-market-mix",
                                    build_market_mix_chart(summary, height=_CHART_H_PRIMARY),
                                    _CHART_H_PRIMARY,
                                ),
                                title_id="title-market-mix",
                                subtitle_id="subtitle-market-mix",
                                panel_id="market-mix",
                            ),
                            _panel(
                                f"Powertrain Share Change ({summary['year'] - 1} → {summary['year']})",
                                "Percentage-point movement vs previous year",
                                _graph(
                                    "chart-share-change",
                                    build_share_change_chart(summary, height=_CHART_H_PRIMARY),
                                    _CHART_H_PRIMARY,
                                ),
                                title_id="title-share-change",
                                panel_id="share-change",
                            ),
                        ],
                    ),
                    html.Div(
                        className="grid grid--secondary",
                        children=[
                            _panel(
                                f"Electrified Vehicle Adoption by Country ({summary['year']})",
                                "Share of registrations that are BEV, PHEV, or HEV",
                                _graph(
                                    "chart-map",
                                    build_map_chart(countries_for_year, "electrified_share_pct"),
                                    _CHART_H_MAP,
                                ),
                                "panel--map",
                                title_id="title-country-map",
                                panel_id="country-map",
                            ),
                            _panel(
                                f"Top 10 vs Bottom 10 Countries by Electrified Share ({summary['year']})",
                                "Countries in the selected market scope",
                                html.Div(
                                    id="country-ranking-table",
                                    children=build_country_ranking_table(
                                        countries_for_year,
                                        metric="electrified_share_pct",
                                        count=10,
                                    ),
                                ),
                                "panel--ranking",
                                title_id="title-country-ranking",
                                panel_id="country-ranking",
                            ),
                            html.Div(
                                className="panel-stack",
                                children=[
                                    _panel(
                                        "Total Market Value",
                                        "Estimated new vehicle market value, billion EUR",
                                        _graph(
                                            "chart-market-value",
                                            build_market_value_chart(value_df, year_from, year_to, height=_CHART_H_BOTTOM),
                                            _CHART_H_BOTTOM,
                                        ),
                                        panel_id="market-value",
                                    ),
                                    _panel(
                                        "BEV & PHEV Sales Share Outlook",
                                        "Observed trends vs IEA STEPS 2025 projection — dashed lines = forecast",
                                        _graph(
                                            "chart-forecast",
                                            build_forecast_chart(data.get("forecast"), year_from=year_from, height=_CHART_H_BOTTOM),
                                            _CHART_H_BOTTOM,
                                        ),
                                        panel_id="forecast",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
