"""
KPI cards for the single-screen EV monitor dashboard.
"""

from __future__ import annotations

from dash import html

from dashboard.analytics import format_delta, format_millions


def _trend_class(value: float) -> str:
    return "positive" if value >= 0 else "negative"


def _share_value(summary: dict, key: str) -> float:
    return float(summary.get("shares", {}).get(key, 0))


def _share_delta(summary: dict, key: str) -> float:
    return float(summary.get("share_deltas", {}).get(key, 0))


def _card(
    title: str,
    value: str,
    year: int,
    delta_text: str,
    delta_value: float,
    icon: str,
    tone: str,
    eyebrow: str | None = None,
) -> html.Div:
    title_block = [html.Div(title, className="kpi-title")]
    if eyebrow:
        title_block.append(html.Div(eyebrow, className="kpi-eyebrow"))

    return html.Div(
        className=f"kpi-card kpi-card--{tone}",
        children=[
            html.Div(className="kpi-icon", children=icon),
            html.Div(
                className="kpi-main",
                children=[
                    html.Div(className="kpi-title-wrap", children=title_block),
                    html.Div(value, className="kpi-value"),
                    html.Div(
                        className="kpi-foot",
                        children=[
                            html.Span(str(year), className="kpi-year"),
                            html.Span(delta_text, className=f"kpi-delta {_trend_class(delta_value)}"),
                        ],
                    ),
                ],
            ),
            html.Span("i", className="kpi-info", title="Compared with previous available year"),
        ],
    )


def build_kpi_cards(summary: dict) -> html.Div:
    year = int(summary.get("year") or 2024)
    total = float(summary.get("total_registrations") or 0)
    total_delta = float(summary.get("total_delta_pct") or 0)
    prev = summary.get("previous_year")
    prev_label = f"vs {prev}" if prev else "vs previous"

    cards = [
        _card(
            "Total New Registrations",
            format_millions(total),
            year,
            f"{total_delta:+.1f}% {prev_label}",
            total_delta,
            "CAR",
            "blue",
        ),
        _card(
            "Electrified Share",
            f"{_share_value(summary, 'Electrified'):.1f}%",
            year,
            f"{format_delta(_share_delta(summary, 'Electrified'))} {prev_label}",
            _share_delta(summary, "Electrified"),
            "EV",
            "green",
            "BEV + PHEV + HEV",
        ),
        _card(
            "BEV Share",
            f"{_share_value(summary, 'BEV'):.1f}%",
            year,
            f"{format_delta(_share_delta(summary, 'BEV'))} {prev_label}",
            _share_delta(summary, "BEV"),
            "BEV",
            "emerald",
        ),
        _card(
            "PHEV Share",
            f"{_share_value(summary, 'PHEV'):.1f}%",
            year,
            f"{format_delta(_share_delta(summary, 'PHEV'))} {prev_label}",
            _share_delta(summary, "PHEV"),
            "PLG",
            "purple",
        ),
        _card(
            "HEV Share",
            f"{_share_value(summary, 'HEV'):.1f}%",
            year,
            f"{format_delta(_share_delta(summary, 'HEV'))} {prev_label}",
            _share_delta(summary, "HEV"),
            "HEV",
            "orange",
        ),
        _card(
            "ICE Share",
            f"{_share_value(summary, 'ICE'):.1f}%",
            year,
            f"{format_delta(_share_delta(summary, 'ICE'))} {prev_label}",
            _share_delta(summary, "ICE"),
            "ICE",
            "red",
            "Petrol + Diesel",
        ),
    ]

    return html.Div(className="kpi-grid", children=cards)
