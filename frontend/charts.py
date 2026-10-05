"""Chart builders with a common visual treatment."""
import plotly.graph_objects as go
import streamlit as st
from theme import ACCENT, DANGER, PLOTLY_LAYOUT, SUCCESS, TEXT, TEXT_MUTED

def show_chart(fig: go.Figure, key: str | None = None) -> None:
    st.plotly_chart(fig, use_container_width=True, key=key, config={"displayModeBar": False, "responsive": True, "scrollZoom": False})

def traffic_donut(labels: list, values: list, height: int = 290) -> go.Figure:
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=.78, sort=False,
        marker=dict(colors=[SUCCESS, DANGER], line=dict(color="#fff", width=5)),
        textinfo="none", hovertemplate="%{label}<br>%{value:,} connections · %{percent}<extra></extra>"))
    fig.update_layout(**PLOTLY_LAYOUT, height=height, showlegend=False,
        annotations=[dict(text=f"<b>{sum(values):,}</b>", x=.5, y=.54, showarrow=False, font=dict(size=25, color=TEXT)),
                     dict(text="BENCHMARK CONNECTIONS", x=.5, y=.40, showarrow=False, font=dict(size=9, color=TEXT_MUTED))])
    return fig

def distribution_chart(normal: list, anomaly: list, title: str, height: int = 370) -> go.Figure:
    fig = go.Figure()
    for name, values, color in [("Normal", normal, SUCCESS), ("Anomaly", anomaly, DANGER)]:
        fig.add_trace(go.Histogram(x=values, name=name, marker_color=color, opacity=.65, nbinsx=45, histnorm="probability density"))
    fig.update_layout(**PLOTLY_LAYOUT, height=height, barmode="overlay", xaxis_title=title, yaxis_title="Density", bargap=.08)
    return fig
