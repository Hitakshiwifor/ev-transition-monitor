"""
dashboard/components/map_view.py
==================================
Europe choropleth map using Plotly Express.
Shows BEV share / registrations per country.
"""

import pandas as pd
import plotly.graph_objects as go

from config.settings import WIFOR_COLORS


def build_map_chart(
    df: pd.DataFrame | None,
    metric: str = "bev_share_pct",
) -> go.Figure:
    """
    Build a Europe choropleth map.

    Parameters
    ----------
    df     : Gold country_bev_share DataFrame
    metric : column to visualise (bev_share_pct | bev_registrations | total_registrations)
    """
    fig = go.Figure()

    if df is None or df.empty:
        fig.add_annotation(
            text="No country data available",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=14, color=WIFOR_COLORS["text_muted"])
        )
        _apply_map_layout(fig)
        return fig

    df = df.copy()
    df = df.dropna(subset=["iso3"])

    label_map = {
        "electrified_share_pct": ("Electrified Share", "%{z:.1f}%", [0, 90]),
        "bev_share_pct": ("BEV Share", "%{z:.1f}%", [0, 90]),
        "bev_registrations": ("BEV Registrations", "%{z:,.0f}", None),
        "total_registrations": ("Total Registrations", "%{z:,.0f}", None),
    }
    title_label, hover_fmt, z_range = label_map.get(
        metric, ("BEV Share", "%{z:.1f}%", [0, 70])
    )

    # WifOR brand colour scale: white → Hellblau → Petrol → Navy
    colorscale = [
        [0.00, "#F4F8FA"],   # near-white
        [0.25, "#C8DCF0"],   # very light blue
        [0.50, "#83B6EF"],   # Hellblau  rgb(131,182,239)
        [0.75, "#77C6BE"],   # Petrol    rgb(119,198,190)
        [1.00, "#003662"],   # WifOR Blau rgb(0,54,98)
    ]

    z_values = df[metric].tolist()
    if z_range is None:
        z_range = [0, max(z_values) if z_values else 1]

    hover_text = []
    for _, row in df.iterrows():
        if metric in {"bev_share_pct", "electrified_share_pct"}:
            detail = (
                f"<b>{row['country_name']}</b><br>"
                f"Electrified Share: {row.get('electrified_share_pct', 0):.1f}%<br>"
                f"BEV Share: {row.get('bev_share_pct', 0):.1f}%<br>"
                f"Total Registrations: {int(row.get('total_registrations', 0)):,}"
            )
        elif metric == "bev_registrations":
            detail = f"<b>{row['country_name']}</b><br>BEV: {int(row.get('bev_registrations', 0)):,}<br>Share: {row.get('bev_share_pct', 0):.1f}%"
        else:
            detail = f"<b>{row['country_name']}</b><br>Total: {int(row.get('total_registrations', 0)):,}"
        hover_text.append(detail)

    fig.add_trace(go.Choropleth(
        locations=df["iso3"],
        locationmode="ISO-3",
        z=z_values,
        text=hover_text,
        hoverinfo="text",
        colorscale=colorscale,
        zmin=z_range[0],
        zmax=z_range[1],
        marker_line_color="white",
        marker_line_width=0.8,
        colorbar=dict(
            title=dict(text=title_label, font=dict(size=10, color="#667085")),
            tickfont=dict(size=9, color="#667085"),
            len=0.58,
            thickness=10,
            x=0.02,
            xanchor="left",
            y=0.40,
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
        ),
    ))

    fig.update_geos(
        scope="europe",
        projection_type="natural earth",
        showframe=False,
        showcoastlines=True,
        coastlinecolor=WIFOR_COLORS["border"],
        showland=True,
        landcolor="#f2f4f7",
        showocean=True,
        oceancolor="#ffffff",
        showlakes=False,
        showcountries=True,
        countrycolor=WIFOR_COLORS["border"],
        lataxis_range=[34, 72],
        lonaxis_range=[-13, 42],
        bgcolor="rgba(0,0,0,0)",
    )

    _apply_map_layout(fig)
    return fig


def _apply_map_layout(fig: go.Figure) -> None:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        geo_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=0, b=0, l=0, r=0),
        font=dict(family="Inter, sans-serif"),
        hoverlabel=dict(
            bgcolor=WIFOR_COLORS["navy"],
            font_color="white",
            font_size=12,
            font_family="Inter, sans-serif",
            bordercolor=WIFOR_COLORS["navy"],
        ),
    )
