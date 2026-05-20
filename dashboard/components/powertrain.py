"""
Powertrain trend chart for the single-screen dashboard.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from dashboard.analytics import DISPLAY_POWERTRAINS, POWERTRAIN_COLORS, POWERTRAIN_LABELS


def _empty_figure(message: str, height: int) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=13, color="#667085"),
    )
    fig.update_layout(**_layout(height))
    return fig


def _layout(height: int = 0) -> dict:
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        margin=dict(t=6, b=32, l=54, r=12),
        font=dict(family="Inter, sans-serif", color="#101828", size=12),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=0.98,
            xanchor="right",
            x=0.99,
            font=dict(size=10),
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="rgba(0,0,0,0.07)",
            borderwidth=1,
            itemwidth=40,
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#071437",
            font_color="white",
            font_size=12,
            font_family="Inter, sans-serif",
            bordercolor="#071437",
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            dtick=1,
            tickfont=dict(size=10, color="#667085"),
            linecolor="#e6eaf2",
            linewidth=1,
        ),
        yaxis=dict(
            title=dict(text="Million registrations", font=dict(size=11, color="#667085")),
            showgrid=True,
            gridcolor="#eef2f7",
            zeroline=False,
            tickfont=dict(size=10, color="#667085"),
            rangemode="tozero",
        ),
    )


def build_powertrain_chart(
    df: pd.DataFrame | None,
    selected_powertrains: list[str] | None = None,
    year_from: int = 2015,
    year_to: int = 2024,
    chart_type: str = "volume",
    height: int = 280,
) -> go.Figure:
    if df is None or df.empty:
        return _empty_figure("No registration data available", height)

    selected = selected_powertrains or DISPLAY_POWERTRAINS
    data = df.copy()
    data["year"] = pd.to_numeric(data["year"], errors="coerce")
    data = data[(data["year"] >= year_from) & (data["year"] <= year_to)]

    if data.empty:
        return _empty_figure("No data in the selected year range", height)

    fig = go.Figure()
    y_col = "share_pct" if chart_type == "share" else "registrations"
    scale = 1 if y_col == "share_pct" else 1_000_000

    trace_order = [pt for pt in DISPLAY_POWERTRAINS if pt in selected]
    if "TOTAL" in selected:
        totals = data.groupby("year", as_index=False)["registrations"].sum()
        fig.add_trace(
            go.Scatter(
                x=totals["year"],
                y=totals["registrations"] / 1_000_000,
                mode="lines+markers",
                name=POWERTRAIN_LABELS["TOTAL"],
                line=dict(color=POWERTRAIN_COLORS["TOTAL"], width=3),
                marker=dict(size=5, color=POWERTRAIN_COLORS["TOTAL"]),
                hovertemplate="<b>Total Market</b>: %{y:.2f}M<extra></extra>",
            )
        )

    for pt in trace_order:
        pt_df = data[data["powertrain"] == pt].sort_values("year")
        if pt_df.empty:
            continue
        suffix = "%" if y_col == "share_pct" else "M"
        value_template = "%{y:.1f}%" if y_col == "share_pct" else "%{y:.2f}M"
        fig.add_trace(
            go.Scatter(
                x=pt_df["year"],
                y=pt_df[y_col] / scale,
                mode="lines+markers",
                name=POWERTRAIN_LABELS.get(pt, pt),
                line=dict(color=POWERTRAIN_COLORS.get(pt, "#667085"), width=2.4),
                marker=dict(
                    size=5,
                    color=POWERTRAIN_COLORS.get(pt, "#667085"),
                    line=dict(color="white", width=1),
                ),
                hovertemplate=f"<b>{POWERTRAIN_LABELS.get(pt, pt)}</b>: {value_template}<extra></extra>",
            )
        )

    layout = _layout(height)
    if y_col == "share_pct":
        layout["yaxis"]["title"] = dict(text="Share of registrations", font=dict(size=11, color="#667085"))
        layout["yaxis"]["ticksuffix"] = suffix
        layout["yaxis"]["range"] = [0, 100]
    fig.update_layout(**layout)
    return fig
