"""Streamlit overview dashboard."""

from __future__ import annotations

import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

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
    render_ranking,
)


st.set_page_config(**PAGE_CONFIG)
render_app_shell("home")

health = dataset_info = compare_info = model_info = None
errors: list[str] = []

for label, path, timeout in (
    ("health", "/health", 5),
    ("dataset", "/api/dataset/info", 12),
    ("models", "/api/models/compare", 20),
    ("prediction", "/api/predict/best_model", 45),
):
    try:
        payload = api_get(path, timeout=timeout)
        if label == "health":
            health = payload
        elif label == "dataset":
            dataset_info = payload
        elif label == "models":
            compare_info = payload
        else:
            model_info = payload
    except Exception as exc:
        errors.append(f"{label}: {explain_api_error(exc)}")

overview = dataset_info.get("overview", {}) if dataset_info else {}
test_set = overview.get("test_set", {})
train_set = overview.get("train_set", {})
label_dist = dataset_info.get("label_distribution", {}) if dataset_info else {}
metrics = compare_info.get("metrics", []) if compare_info else []
best_model = model_info.get("best_model", {}) if model_info else {}
best_metrics = best_model.get("metrics", {})

render_page_header(
    "NetGuard Operations",
    "Live anomaly detection dashboard",
    "UNSW-NB15 traffic, ensemble scoring, and single-connection inference in one dark control surface.",
    [
        "API online" if health and health.get("status") == "ok" else "API pending",
        best_model.get("name", "Model unavailable"),
        f"{len(metrics)} models" if metrics else "",
    ],
)

if errors:
    render_callout("Some backend data is unavailable: " + " | ".join(errors), "warning")

render_metric_cards(
    [
        {
            "label": "Train rows",
            "value": f"{train_set.get('n_rows', 0):,}" if train_set else "-",
            "sub": "featured training traffic",
            "tone": "accent",
        },
        {
            "label": "Test rows",
            "value": f"{test_set.get('n_rows', 0):,}" if test_set else "-",
            "sub": f"{format_percent(test_set.get('anomaly_rate'))} anomalies" if test_set else "-",
        },
        {
            "label": "Best F1",
            "value": format_number(best_metrics.get("f1")),
            "sub": best_model.get("name", "deployed model"),
            "tone": "success",
        },
        {
            "label": "ROC-AUC",
            "value": format_number(best_metrics.get("roc_auc")),
            "sub": "model separation",
            "tone": "accent",
        },
    ]
)

left, right = st.columns([1.05, 0.95], gap="large")

with left:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">Model ranking</div>
            <div class="panel-heading">Composite score leaderboard</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if metrics:
        render_ranking(metrics)
    else:
        render_callout("Model comparison is not loaded yet.", "warning")

with right:
    render_kv_panel(
        "Backend",
        "Service state",
        [
            ("URL", os.getenv("BACKEND_URL", "http://localhost:5000")),
            ("Status", health.get("status", "unknown") if health else "offline"),
            ("Version", health.get("version", "-") if health else "-"),
            ("Models ready", health.get("models_ready", "-") if health else "-"),
        ],
    )
    if best_model:
        render_kv_panel(
            "Deployment",
            "Current ensemble",
            [
                ("Threshold", best_model.get("threshold", "-")),
                ("Contamination", format_number(best_model.get("contamination"))),
                ("Precision", format_number(best_metrics.get("precision"))),
                ("Recall", format_number(best_metrics.get("recall"))),
            ],
        )

if label_dist.get("pie_chart"):
    chart_col, table_col = st.columns([0.9, 1.1], gap="large")
    pie = label_dist["pie_chart"]
    with chart_col:
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
        fig.update_layout(**PLOTLY_LAYOUT, height=330, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    with table_col:
        if metrics:
            df = pd.DataFrame(metrics)
            display_cols = [col for col in ["model", "roc_auc", "f1", "recall", "precision", "perf_score"] if col in df]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
