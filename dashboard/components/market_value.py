"""
Market value bar chart.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def build_market_value_chart(
    df: pd.DataFrame | None,
    year_from: int | None = None,
    year_to: int | None = None,
    height: int = 180,
) -> go.Figure:
    fig = go.Figure()

    if df is None or df.empty:
        fig.add_annotation(
            text="No market value data available",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=13, color="#667085"),
        )
        _apply_layout(fig, height)
        return fig

    data = df.sort_values("year").copy()
    if year_from is not None:
        data = data[data["year"] >= year_from]
    if year_to is not None:
        data = data[data["year"] <= year_to]

    if data.empty:
        fig.add_annotation(
            text="No data in selected range",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=13, color="#667085"),
        )
        _apply_layout(fig, height)
        return fig

    fig.add_trace(
        go.Bar(
            x=data["year"],
            y=data["market_value_eur_bn"],
            name="Market Value",
            marker=dict(color="#2f7df6", line=dict(width=0), cornerradius=3),
            hovertemplate="<b>%{x}</b><br>Market value: EUR %{y:.1f} bn<extra></extra>",
            text=data["market_value_eur_bn"].apply(lambda value: f"{value:.0f}"),
            textposition="outside",
            textfont=dict(size=9, color="#344054"),
            cliponaxis=False,
        )
    )
    _apply_layout(fig, height)
    return fig


def _apply_layout(fig: go.Figure, height: int) -> None:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        font=dict(family="Inter, sans-serif", color="#101828", size=12),
        margin=dict(t=16, b=28, l=46, r=12),
        showlegend=False,
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
            title=dict(text="Billion EUR", font=dict(size=10, color="#667085")),
            showgrid=True,
            gridcolor="#eef2f7",
            zeroline=False,
            tickfont=dict(size=9, color="#667085"),
            rangemode="tozero",
        ),
    )
