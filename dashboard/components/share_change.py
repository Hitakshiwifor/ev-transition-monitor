"""
Powertrain share-change chart.
"""

from __future__ import annotations

import plotly.graph_objects as go

from dashboard.analytics import POWERTRAIN_COLORS, POWERTRAIN_LABELS

CHANGE_ORDER = ["BEV", "PHEV", "HEV", "ICE_Petrol", "ICE_Diesel"]


def build_share_change_chart(summary: dict, height: int = 220) -> go.Figure:
    deltas = summary.get("share_deltas", {})
    labels = [POWERTRAIN_LABELS[key] for key in CHANGE_ORDER]
    values = [float(deltas.get(key, 0)) for key in CHANGE_ORDER]
    colors = [POWERTRAIN_COLORS[key] for key in CHANGE_ORDER]
    max_abs = max([abs(value) for value in values] + [1])

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=colors, line=dict(width=0), cornerradius=3),
            text=[f"{value:+.1f} pp" for value in values],
            textposition=["outside" if value >= 0 else "outside" for value in values],
            textfont=dict(size=10, color="#344054"),
            hovertemplate="<b>%{y}</b><br>Change: %{x:+.1f} pp<extra></extra>",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        bargap=0.28,
        margin=dict(t=6, b=28, l=68, r=52),
        font=dict(family="Inter, sans-serif", color="#101828", size=12),
        showlegend=False,
        xaxis=dict(
            title=dict(text="Percentage points", font=dict(size=10, color="#667085")),
            range=[-max_abs * 1.25, max_abs * 1.25],
            zeroline=True,
            zerolinecolor="#98a2b3",
            zerolinewidth=1,
            showgrid=True,
            gridcolor="#eef2f7",
            tickfont=dict(size=10, color="#667085"),
        ),
        yaxis=dict(
            autorange="reversed",
            showgrid=False,
            tickfont=dict(size=11, color="#344054"),
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
