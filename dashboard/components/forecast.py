"""
BEV and PHEV sales-share outlook chart.
Shows observed trends (2013-2024) and IEA STEPS 2025 projections (2025-2030).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def build_forecast_chart(
    df: pd.DataFrame | None,
    year_from: int | None = 2015,
    height: int = 260,
) -> go.Figure:
    fig = go.Figure()
    if df is None or df.empty:
        fig.add_annotation(
            text="No forecast data available",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=13, color="#667085"),
        )
        _apply_layout(fig, height)
        return fig

    data = df.copy()
    data = data[data["powertrain"].isin(["BEV", "PHEV"])]
    if year_from is not None:
        data = data[data["year"] >= int(year_from)]

    if data.empty:
        fig.add_annotation(
            text="No outlook data in selected range",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=13, color="#667085"),
        )
        _apply_layout(fig, height)
        return fig

    bev_actual  = data[(data["powertrain"] == "BEV")  & (data["series_type"] == "actual")].sort_values("year")
    bev_proj    = data[(data["powertrain"] == "BEV")  & (data["series_type"] == "projection")].sort_values("year")
    phev_actual = data[(data["powertrain"] == "PHEV") & (data["series_type"] == "actual")].sort_values("year")
    phev_proj   = data[(data["powertrain"] == "PHEV") & (data["series_type"] == "projection")].sort_values("year")

    all_proj = data[data["series_type"] == "projection"]
    if not all_proj.empty:
        fig.add_vrect(
            x0=float(all_proj["year"].min()) - 0.5,
            x1=float(all_proj["year"].max()) + 0.5,
            fillcolor="#f5f0ff",
            opacity=0.5,
            line_width=0,
            layer="below",
        )
        fig.add_annotation(
            x=float(all_proj["year"].median()),
            y=40,
            text="IEA STEPS Projection",
            showarrow=False,
            font=dict(size=10, color="#8b45d9"),
            xanchor="center",
        )

    fig.add_vline(x=2024.5, line_width=1, line_dash="dot", line_color="#c5cedb")

    if not bev_actual.empty:
        fig.add_trace(go.Scatter(
            x=bev_actual["year"],
            y=bev_actual["ev_sales_share_pct"],
            mode="lines+markers",
            name="BEV (Observed)",
            line=dict(color="#0aa15f", width=2.4),
            marker=dict(size=5, color="#0aa15f", line=dict(color="white", width=1)),
            hovertemplate="<b>BEV Observed</b><br>%{x}: %{y:.1f}%<extra></extra>",
        ))
    if not bev_proj.empty:
        fig.add_trace(go.Scatter(
            x=bev_proj["year"],
            y=bev_proj["ev_sales_share_pct"],
            mode="lines+markers",
            name="BEV STEPS 2025",
            line=dict(color="#0aa15f", width=2.2, dash="dash"),
            marker=dict(size=4, color="#0aa15f", line=dict(color="white", width=1)),
            hovertemplate="<b>BEV STEPS</b><br>%{x}: %{y:.1f}%<extra></extra>",
        ))
    if not phev_actual.empty:
        fig.add_trace(go.Scatter(
            x=phev_actual["year"],
            y=phev_actual["ev_sales_share_pct"],
            mode="lines+markers",
            name="PHEV (Observed)",
            line=dict(color="#8b45d9", width=2.4),
            marker=dict(size=5, color="#8b45d9", line=dict(color="white", width=1)),
            hovertemplate="<b>PHEV Observed</b><br>%{x}: %{y:.1f}%<extra></extra>",
        ))
    if not phev_proj.empty:
        fig.add_trace(go.Scatter(
            x=phev_proj["year"],
            y=phev_proj["ev_sales_share_pct"],
            mode="lines+markers",
            name="PHEV STEPS 2025",
            line=dict(color="#8b45d9", width=2.2, dash="dash"),
            marker=dict(size=4, color="#8b45d9", line=dict(color="white", width=1)),
            hovertemplate="<b>PHEV STEPS</b><br>%{x}: %{y:.1f}%<extra></extra>",
        ))

    _apply_layout(fig, height)
    return fig


def _apply_layout(fig: go.Figure, height: int) -> None:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        font=dict(family="Inter, sans-serif", color="#101828", size=12),
        margin=dict(t=16, b=32, l=48, r=16),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1,
            font=dict(size=10),
            bgcolor="rgba(0,0,0,0)",
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
            tickfont=dict(size=9, color="#667085"),
            linecolor="#e6eaf2",
            linewidth=1,
            dtick=2,
        ),
        yaxis=dict(
            title=dict(text="Share of new car sales", font=dict(size=10, color="#667085")),
            showgrid=True,
            gridcolor="#eef2f7",
            zeroline=False,
            ticksuffix="%",
            tickfont=dict(size=9, color="#667085"),
            range=[0, 44],
        ),
    )
