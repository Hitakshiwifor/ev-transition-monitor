"""
dashboard/components/country_ranking.py
==========================================
Horizontal bar chart: Top 5 leaders + Bottom 5 laggards by BEV share.

Leaders are shown in teal, laggards in orange/red.
Data source: gold/country_bev_share.parquet for the latest year.
"""

import pandas as pd
import plotly.graph_objects as go
from dash import html

from config.settings import WIFOR_COLORS


def build_country_ranking_chart(
    df: pd.DataFrame | None,
    metric: str = "bev_share_pct",
    year: int | None = None,
    height: int = 260,
) -> go.Figure:
    """
    Parameters
    ----------
    df     : Gold country_bev_share DataFrame
    metric : column to rank by ('bev_share_pct' | 'bev_registrations')
    year   : filter to this year; if None, uses the latest year in the data
    height : figure height in px
    """
    fig = go.Figure()

    if df is None or df.empty:
        fig.add_annotation(
            text="No country ranking data available",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=13, color=WIFOR_COLORS["text_muted"])
        )
        _apply_layout(fig, metric, height=height)
        return fig

    df = df.copy()

    # Filter to requested year (or latest)
    if year is not None and year in df["year"].values:
        df = df[df["year"] == year]
    else:
        latest = df["year"].max()
        df = df[df["year"] == latest]

    if df.empty or metric not in df.columns:
        fig.add_annotation(
            text="Insufficient data for ranking",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=13, color=WIFOR_COLORS["text_muted"])
        )
        _apply_layout(fig, metric, height=height)
        return fig

    df = df.dropna(subset=[metric]).sort_values(metric, ascending=False)

    top5    = df.head(5).iloc[::-1]   # reverse so highest is at top of chart
    bottom5 = df.tail(5)              # lowest first -> plotly shows bottom at top

    # Build separator with NaN numerics to avoid FutureWarning in pd.concat
    sep_data = {c: [float("nan")] for c in bottom5.columns}
    sep_data["country_name"] = [""]
    separator = pd.DataFrame(sep_data)

    combined = pd.concat([bottom5, separator, top5], ignore_index=True)

    names  = combined["country_name"].tolist()
    values = combined[metric].tolist()

    n_bottom = len(bottom5)
    n_sep    = 1
    n_top    = len(top5)
    bar_colors = (
        [WIFOR_COLORS["orange"]] * n_bottom   +   # laggards
        ["rgba(0,0,0,0)"]        * n_sep       +   # invisible separator
        [WIFOR_COLORS["teal"]]   * n_top           # leaders
    )

    # Hover text
    def _hover(row):
        if pd.isna(row.get(metric)):
            return ""
        if metric == "bev_share_pct":
            share = row.get("bev_share_pct", 0) or 0
            total = row.get("total_registrations", 0) or 0
            bev   = int(total * share / 100) if total else 0
            return (
                f"<b>{row['country_name']}</b><br>"
                f"BEV Share: {share:.1f}%<br>"
                f"BEV Registrations: {bev:,}"
            )
        else:
            val = row.get(metric, 0) or 0
            return f"<b>{row['country_name']}</b><br>BEV Registrations: {int(val):,}"

    hover_texts = [_hover(row) for _, row in combined.iterrows()]

    plot_values = [v if v is not None and not (isinstance(v, float) and pd.isna(v)) else 0
                   for v in values]

    x_suffix = "%" if metric == "bev_share_pct" else ""

    fig.add_trace(go.Bar(
        x=plot_values,
        y=names,
        orientation="h",
        marker=dict(
            color=bar_colors,
            line=dict(color="rgba(0,0,0,0)", width=0),
            cornerradius=4,
        ),
        text=[
            f"{v:.1f}{x_suffix}" if (v and v > 0) else ""
            for v in plot_values
        ],
        textposition="outside",
        textfont=dict(size=9, color=WIFOR_COLORS["text_muted"]),
        hovertext=hover_texts,
        hoverinfo="text",
        cliponaxis=False,
    ))

    # Dotted divider between bottom5 and top5
    fig.add_shape(
        type="line",
        x0=0, x1=1, xref="paper",
        y0=n_bottom + 0.5, y1=n_bottom + 0.5, yref="y",
        line=dict(color=WIFOR_COLORS["border"], width=1, dash="dot"),
    )

    # Section labels
    fig.add_annotation(
        text="🏆 Leaders", x=1, y=n_bottom + n_sep + n_top - 0.6,
        xref="paper", yref="y",
        showarrow=False,
        font=dict(size=9, color=WIFOR_COLORS["teal"]),
        xanchor="right",
    )
    fig.add_annotation(
        text="⚠ Laggards", x=1, y=n_bottom - 0.6,
        xref="paper", yref="y",
        showarrow=False,
        font=dict(size=9, color=WIFOR_COLORS["orange"]),
        xanchor="right",
    )

    _apply_layout(fig, metric, height=height)
    return fig


def _apply_layout(fig: go.Figure, metric: str, height: int = 260) -> None:
    x_suffix = "%" if metric == "bev_share_pct" else ""
    fig.update_layout(
        height=height,
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        # Generous right margin so value labels (e.g. "87.9%") don't clip
        margin=dict(t=6, b=6, l=4, r=56),
        font=dict(family="Inter, sans-serif"),
        showlegend=False,
        xaxis=dict(
            # No title — card description already says "BEV Market Share (%)"
            title=None,
            ticksuffix=x_suffix,
            tickfont=dict(size=9, color=WIFOR_COLORS["text_muted"]),
            tickangle=0,
            showgrid=True,
            gridcolor=WIFOR_COLORS["border"],
            gridwidth=1,
            zeroline=False,
            automargin=False,
        ),
        yaxis=dict(
            tickfont=dict(size=10, color=WIFOR_COLORS["navy"]),
            showgrid=False,
            automargin=True,
        ),
        hoverlabel=dict(
            bgcolor=WIFOR_COLORS["navy"],
            font_color="white",
            font_size=12,
            font_family="Inter, sans-serif",
            bordercolor=WIFOR_COLORS["navy"],
        ),
        bargap=0.30,
    )


def build_country_ranking_table(
    df: pd.DataFrame | None,
    metric: str = "electrified_share_pct",
    count: int = 10,
) -> html.Div:
    if df is None or df.empty or metric not in df.columns:
        return html.Div("No country ranking data available", className="empty-state")

    data = df.dropna(subset=[metric]).sort_values(metric, ascending=False).copy()
    if data.empty:
        return html.Div("No country ranking data available", className="empty-state")

    top = data.head(count).reset_index(drop=True)
    bottom = data.tail(count).sort_values(metric, ascending=True).reset_index(drop=True)
    max_value = max(float(data[metric].max()), 1)

    def rows(frame: pd.DataFrame, kind: str, start_rank: int = 1) -> list[html.Div]:
        built = []
        for idx, row in frame.iterrows():
            value = float(row[metric])
            width = max(6, min(100, value / max_value * 100))
            rank = start_rank + idx
            if kind == "bottom":
                rank = len(data) - idx
            built.append(
                html.Div(
                    className="ranking-row",
                    children=[
                        html.Span(str(rank), className="ranking-rank"),
                        html.Span(row["country_name"], className="ranking-country"),
                        html.Div(
                            className="ranking-bar-track",
                            children=html.Span(
                                className=f"ranking-bar ranking-bar--{kind}",
                                style={"width": f"{width}%"},
                            ),
                        ),
                        html.Span(f"{value:.1f}%", className="ranking-value"),
                    ],
                )
            )
        return built

    return html.Div(
        className="ranking-table",
        children=[
            html.Div(
                className="ranking-column",
                children=[
                    html.Div(
                        className="ranking-heading ranking-heading--top",
                        children=[html.Span("Top 10"), html.Span("Share")],
                    ),
                    *rows(top, "top", 1),
                ],
            ),
            html.Div(
                className="ranking-column",
                children=[
                    html.Div(
                        className="ranking-heading ranking-heading--bottom",
                        children=[html.Span("Bottom 10"), html.Span("Share")],
                    ),
                    *rows(bottom, "bottom"),
                ],
            ),
        ],
    )
