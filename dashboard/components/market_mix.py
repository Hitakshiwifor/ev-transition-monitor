"""
Current-year powertrain market mix donut.
"""

from __future__ import annotations

import plotly.graph_objects as go

from dashboard.analytics import POWERTRAIN_COLORS, POWERTRAIN_LABELS, format_millions

MIX_ORDER = ["BEV", "PHEV", "HEV", "ICE_Petrol", "ICE_Diesel"]


def build_market_mix_chart(summary: dict, height: int = 220) -> go.Figure:
    shares = summary.get("shares", {})
    registrations = summary.get("registrations", {})
    total = float(summary.get("total_registrations") or 0)
    year = summary.get("year", "")

    values = [float(shares.get(key, 0)) for key in MIX_ORDER]
    labels = [POWERTRAIN_LABELS[key] for key in MIX_ORDER]
    colors = [POWERTRAIN_COLORS[key] for key in MIX_ORDER]
    hover = [
        (
            f"<b>{POWERTRAIN_LABELS[key]}</b><br>"
            f"Share: {float(shares.get(key, 0)):.1f}%<br>"
            f"Registrations: {format_millions(float(registrations.get(key, 0)))}"
        )
        for key in MIX_ORDER
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            marker=dict(colors=colors, line=dict(color="white", width=2)),
            textinfo="none",
            hovertext=hover,
            hoverinfo="text",
            sort=False,
            direction="clockwise",
            rotation=90,
        )
    )
    fig.add_annotation(
        text=f"<b>{format_millions(total)}</b><br><span style='font-size:10px;color:#667085'>{year}</span>",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=16, color="#071437", family="Inter, sans-serif"),
        align="center",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        margin=dict(t=4, b=56, l=4, r=4),
        font=dict(family="Inter, sans-serif"),
        showlegend=True,
        legend=dict(
            orientation="h",
            x=0.5,
            y=-0.02,
            xanchor="center",
            yanchor="top",
            font=dict(size=10, color="#344054"),
            bgcolor="rgba(0,0,0,0)",
            traceorder="normal",
        ),
        hoverlabel=dict(
            bgcolor="#071437",
            font_color="white",
            font_size=12,
            font_family="Inter, sans-serif",
            bordercolor="#071437",
        ),
    )
    return fig
