"""Reusable Plotly chart-building functions."""

import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Any, Optional


def time_series_line(data: List[Dict], x_key: str, y_key: str,
                     title: str, color: str = "#1f77b4") -> go.Figure:
    """Single-line time series chart."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[d[x_key] for d in data],
        y=[d[y_key] for d in data],
        mode="lines+markers",
        name=y_key,
        line=dict(color=color, width=2),
        marker=dict(size=4),
    ))
    fig.update_layout(
        title=title,
        xaxis_title=x_key,
        yaxis_title=y_key,
        template="plotly_white",
        height=300,
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


def multi_line(data: List[Dict], x_key: str, y_keys: List[str],
               title: str, colors: Optional[List[str]] = None) -> go.Figure:
    """Multi-line time series chart."""
    if colors is None:
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    fig = go.Figure()
    for i, key in enumerate(y_keys):
        fig.add_trace(go.Scatter(
            x=[d[x_key] for d in data],
            y=[d.get(key, 0) for d in data],
            mode="lines+markers",
            name=key,
            line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=3),
        ))
    fig.update_layout(
        title=title,
        xaxis_title=x_key,
        yaxis_title="Value",
        template="plotly_white",
        height=350,
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def gauge_chart(value: float, title: str, min_v: float = 0,
                max_v: float = 100, threshold: float = 50) -> go.Figure:
    """Single-value gauge."""
    color = "green" if value >= threshold else "orange" if value >= threshold * 0.6 else "red"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(suffix="", font=dict(size=24)),
        gauge=dict(
            axis=dict(range=[min_v, max_v], tickwidth=1),
            bar=dict(color=color),
            steps=[
                dict(range=[min_v, threshold * 0.6], color="rgba(255,0,0,0.1)"),
                dict(range=[threshold * 0.6, threshold], color="rgba(255,165,0,0.1)"),
                dict(range=[threshold, max_v], color="rgba(0,128,0,0.1)"),
            ],
        ),
    ))
    fig.update_layout(
        title=title,
        height=200,
        margin=dict(l=40, r=40, t=40, b=20),
    )
    return fig


def bar_chart(labels: List[str], values: List[float], title: str,
              color: str = "#1f77b4") -> go.Figure:
    """Simple bar chart."""
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=color,
    ))
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=300,
        margin=dict(l=40, r=20, t=40, b=80),
    )
    return fig


def scatter_plot(data: List[Dict], x_key: str, y_key: str,
                 title: str, color_key: Optional[str] = None) -> go.Figure:
    """Scatter plot of two citizen attributes."""
    fig = px.scatter(
        data_frame=data,
        x=x_key, y=y_key,
        color=color_key,
        title=title,
        template="plotly_white",
        height=400,
    )
    fig.update_traces(marker=dict(size=8, opacity=0.7))
    return fig
