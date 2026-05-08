"""Dataset exploration page."""

from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (  # noqa: E402
    ACCENT,
    DANGER,
    PAGE_CONFIG,
    PLOTLY_LAYOUT,
    SUCCESS,
    api_get,
    explain_api_error,
    format_number,
    format_percent,
    render_app_shell,
    render_callout,
    render_kv_panel,
    render_metric_cards,
    render_page_header,
    render_tags,
)


st.set_page_config(**PAGE_CONFIG)
render_app_shell("dataset")

try:
    info = api_get("/api/dataset/info", timeout=15)
except Exception as exc:
    render_callout(f"Dataset endpoint failed: {explain_api_error(exc)}", "danger")
    st.stop()

overview = info.get("overview", {})
test_set = overview.get("test_set", {})
train_set = overview.get("train_set", {})
feature_names = overview.get("feature_names", [])
numeric_stats = overview.get("numeric_stats", {})
label_dist = info.get("label_distribution", {})
source_file = info.get("source_file", "-")

render_page_header(
    "Dataset UNSW-NB15",
    "Traffic profile",
    "Featured network connections used by the API for evaluation, ranking, and inference calibration.",
    [
        f"{test_set.get('n_rows', 0):,} test rows",
        f"{test_set.get('n_features', 0)} features",
        f"{format_percent(test_set.get('anomaly_rate'))} anomalies",
    ],
)

render_metric_cards(
    [
        {
            "label": "Train rows",
            "value": f"{train_set.get('n_rows', 0):,}",
            "sub": "training set",
            "tone": "accent",
        },
        {
            "label": "Test rows",
            "value": f"{test_set.get('n_rows', 0):,}",
            "sub": source_file,
        },
        {
            "label": "Normal",
            "value": f"{test_set.get('n_normal', 0):,}",
            "sub": "test-set baseline",
            "tone": "success",
        },
        {
            "label": "Anomaly",
            "value": f"{test_set.get('n_anomalies', 0):,}",
            "sub": "positive class",
            "tone": "danger",
        },
    ]
)

left, right = st.columns([0.9, 1.1], gap="large")
with left:
    render_kv_panel(
        "Source",
        "Featured test frame",
        [
            ("File", source_file),
            ("Rows", f"{test_set.get('n_rows', 0):,}"),
            ("Features", test_set.get("n_features", 0)),
            ("Anomaly rate", format_percent(test_set.get("anomaly_rate"))),
        ],
    )
with right:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">Feature set</div>
            <div class="panel-heading">Model input columns</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_tags(feature_names)

tab_classes, tab_distribution, tab_stats, tab_sample = st.tabs(
    ["Classes", "Distributions", "Statistics", "Sample"]
)

with tab_classes:
    pie = label_dist.get("pie_chart", {})
    if pie:
        pie_col, bar_col = st.columns(2, gap="large")
        with pie_col:
            fig = go.Figure(
                go.Pie(
                    labels=pie["labels"],
                    values=pie["values"],
                    hole=0.62,
                    marker=dict(colors=[SUCCESS, DANGER], line=dict(color="#070b12", width=3)),
                    textinfo="percent",
                    textfont=dict(color="#e5edf7"),
                )
            )
            fig.update_layout(**PLOTLY_LAYOUT, height=360)
            st.plotly_chart(fig, use_container_width=True)
        with bar_col:
            fig = go.Figure(
                go.Bar(
                    x=pie["labels"],
                    y=pie["values"],
                    marker=dict(color=[SUCCESS, DANGER]),
                    text=[f"{value:,}" for value in pie["values"]],
                    textposition="outside",
                )
            )
            fig.update_layout(**PLOTLY_LAYOUT, height=360, showlegend=False, yaxis_title="Rows")
            st.plotly_chart(fig, use_container_width=True)

with tab_distribution:
    try:
        dist_payload = api_get("/api/dataset/distributions", params={"top_n": 12}, timeout=20)
    except Exception as exc:
        render_callout(f"Distribution endpoint failed: {explain_api_error(exc)}", "danger")
    else:
        distributions = dist_payload.get("distributions", {})
        if distributions:
            selected = st.selectbox("Feature", list(distributions.keys()))
            payload = distributions[selected]
            normal = payload.get("normal", [])
            anomaly = payload.get("anomaly", [])
            chart_col, detail_col = st.columns([1.2, 0.8], gap="large")
            with chart_col:
                fig = go.Figure()
                fig.add_trace(
                    go.Histogram(
                        x=normal,
                        name="Normal",
                        marker_color=SUCCESS,
                        opacity=0.68,
                        nbinsx=45,
                        histnorm="probability density",
                    )
                )
                fig.add_trace(
                    go.Histogram(
                        x=anomaly,
                        name="Anomaly",
                        marker_color=DANGER,
                        opacity=0.58,
                        nbinsx=45,
                        histnorm="probability density",
                    )
                )
                fig.update_layout(
                    **PLOTLY_LAYOUT,
                    height=420,
                    barmode="overlay",
                    xaxis_title=selected,
                    yaxis_title="Density",
                )
                st.plotly_chart(fig, use_container_width=True)
            with detail_col:
                render_kv_panel(
                    "Normal stats",
                    selected,
                    [(key, format_number(value)) for key, value in payload.get("stats_normal", {}).items()],
                )
                render_kv_panel(
                    "Anomaly stats",
                    selected,
                    [(key, format_number(value)) for key, value in payload.get("stats_anomaly", {}).items()],
                )
        else:
            render_callout("No distributions returned by the backend.", "warning")

with tab_stats:
    if numeric_stats:
        df_stats = pd.DataFrame(numeric_stats).T.reset_index().rename(columns={"index": "feature"})
        st.dataframe(df_stats, use_container_width=True, hide_index=True)
    else:
        render_callout("No numeric statistics available.", "warning")

with tab_sample:
    n_rows = st.slider("Rows", min_value=25, max_value=300, value=100, step=25)
    try:
        sample = api_get("/api/dataset/sample", params={"n": n_rows}, timeout=15).get("sample", [])
    except Exception as exc:
        render_callout(f"Sample endpoint failed: {explain_api_error(exc)}", "danger")
    else:
        st.dataframe(pd.DataFrame(sample), use_container_width=True, hide_index=True)
