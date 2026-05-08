"""Model performance comparison page."""

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
    PALETTE,
    PLOTLY_LAYOUT,
    SUCCESS,
    WARNING,
    api_get,
    explain_api_error,
    format_number,
    render_app_shell,
    render_callout,
    render_kv_panel,
    render_metric_cards,
    render_page_header,
    render_ranking,
)


st.set_page_config(**PAGE_CONFIG)
render_app_shell("performance")

try:
    compare = api_get("/api/models/compare", timeout=30)
except Exception as exc:
    render_callout(f"Model comparison endpoint failed: {explain_api_error(exc)}", "danger")
    st.stop()

metrics = compare.get("metrics", [])
if not metrics:
    render_callout("No model metrics were returned by the backend.", "warning")
    st.stop()

df_metrics = pd.DataFrame(metrics)
if "perf_score" in df_metrics.columns:
    df_metrics = df_metrics.sort_values("perf_score", ascending=False).reset_index(drop=True)

best = df_metrics.iloc[0].to_dict()
model_names = df_metrics["model"].tolist()

render_page_header(
    "Model Performance",
    "Evaluation board",
    "The deployed ensemble is ranked against the available anomaly detectors on the same featured test set.",
    [
        compare.get("source", "-"),
        f"{len(df_metrics)} models",
        best.get("model", "best model"),
    ],
)

render_metric_cards(
    [
        {
            "label": "Best F1",
            "value": format_number(best.get("f1")),
            "sub": best.get("model", ""),
            "tone": "success",
        },
        {
            "label": "ROC-AUC",
            "value": format_number(best.get("roc_auc")),
            "sub": "separation quality",
            "tone": "accent",
        },
        {
            "label": "Recall",
            "value": format_number(best.get("recall")),
            "sub": "attack coverage",
        },
        {
            "label": "Composite",
            "value": format_number(best.get("perf_score")),
            "sub": "selection score",
            "tone": "accent",
        },
    ]
)

left, right = st.columns([0.95, 1.05], gap="large")
with left:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">Ranking</div>
            <div class="panel-heading">Composite performance</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_ranking(df_metrics.to_dict(orient="records"))

with right:
    render_kv_panel(
        "Best model",
        best.get("model", "-"),
        [
            ("F1", format_number(best.get("f1"))),
            ("ROC-AUC", format_number(best.get("roc_auc"))),
            ("Precision", format_number(best.get("precision"))),
            ("Recall", format_number(best.get("recall"))),
            ("Inference", f"{format_number(best.get('inference_s'))} s"),
        ],
    )

tab_table, tab_roc, tab_confusion, tab_scores, tab_pca = st.tabs(
    ["Table", "ROC", "Confusion", "Scores", "PCA"]
)

with tab_table:
    columns = [
        col
        for col in [
            "model",
            "roc_auc",
            "f1",
            "recall",
            "precision",
            "avg_precision",
            "inference_s",
            "perf_score",
        ]
        if col in df_metrics.columns
    ]
    st.dataframe(df_metrics[columns], use_container_width=True, hide_index=True)

with tab_roc:
    with st.spinner("Loading ROC curves..."):
        try:
            roc_payload = api_get("/api/models/viz", params={"type": "roc"}, timeout=160)
        except Exception as exc:
            render_callout(f"ROC endpoint failed: {explain_api_error(exc)}", "danger")
        else:
            curves = roc_payload.get("data", {})
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=[0, 1],
                    y=[0, 1],
                    mode="lines",
                    name="Random",
                    line=dict(color="#64748b", dash="dash", width=1.4),
                )
            )
            for idx, (name, curve) in enumerate(curves.items()):
                fig.add_trace(
                    go.Scatter(
                        x=curve.get("fpr", []),
                        y=curve.get("tpr", []),
                        mode="lines",
                        name=name,
                        line=dict(color=PALETTE[idx % len(PALETTE)], width=2.4),
                    )
                )
            fig.update_layout(
                **PLOTLY_LAYOUT,
                height=500,
                xaxis_title="False positive rate",
                yaxis_title="True positive rate",
            )
            st.plotly_chart(fig, use_container_width=True)

with tab_confusion:
    with st.spinner("Loading confusion matrices..."):
        try:
            cm_payload = api_get("/api/models/viz", params={"type": "confusion"}, timeout=160)
        except Exception as exc:
            render_callout(f"Confusion endpoint failed: {explain_api_error(exc)}", "danger")
        else:
            matrices = cm_payload.get("data", [])
            selected = st.selectbox("Model", [m.get("model_name", "") for m in matrices])
            matrix = next((m for m in matrices if m.get("model_name") == selected), None)
            if matrix:
                heat = go.Figure(
                    go.Heatmap(
                        z=matrix["z"],
                        x=matrix.get("x", ["Pred normal", "Pred anomaly"]),
                        y=matrix.get("y", ["Real normal", "Real anomaly"]),
                        colorscale=[[0, "#111d2e"], [0.55, ACCENT], [1, SUCCESS]],
                        text=[[f"{value:,}" for value in row] for row in matrix["z"]],
                        texttemplate="%{text}",
                        showscale=False,
                    )
                )
                heat.update_layout(
                    **PLOTLY_LAYOUT,
                    height=420,
                    title=f"{selected} | F1 {format_number(matrix.get('f1'))} | AUC {format_number(matrix.get('roc_auc'))}",
                )
                st.plotly_chart(heat, use_container_width=True)

with tab_scores:
    with st.spinner("Loading score distributions..."):
        try:
            score_payload = api_get("/api/models/viz", params={"type": "scores"}, timeout=160)
        except Exception as exc:
            render_callout(f"Score endpoint failed: {explain_api_error(exc)}", "danger")
        else:
            distributions = score_payload.get("data", {})
            selected = st.selectbox("Score model", list(distributions.keys()))
            data = distributions[selected]
            chart_col, info_col = st.columns([1.2, 0.8], gap="large")
            with chart_col:
                fig = go.Figure()
                fig.add_trace(
                    go.Histogram(
                        x=data.get("normal", []),
                        name="Normal",
                        marker_color=SUCCESS,
                        opacity=0.65,
                        nbinsx=50,
                        histnorm="probability density",
                    )
                )
                fig.add_trace(
                    go.Histogram(
                        x=data.get("anomaly", []),
                        name="Anomaly",
                        marker_color=DANGER,
                        opacity=0.55,
                        nbinsx=50,
                        histnorm="probability density",
                    )
                )
                fig.update_layout(
                    **PLOTLY_LAYOUT,
                    height=430,
                    barmode="overlay",
                    xaxis_title="Anomaly score",
                    yaxis_title="Density",
                )
                st.plotly_chart(fig, use_container_width=True)
            with info_col:
                render_kv_panel(
                    "Percentiles",
                    selected,
                    [(key.upper(), format_number(value)) for key, value in data.get("percentiles", {}).items()],
                )

with tab_pca:
    model_choice = st.selectbox("PCA model", model_names, index=0)
    with st.spinner("Loading PCA projection..."):
        try:
            pca_payload = api_get(
                "/api/models/viz",
                params={"type": "pca", "model": model_choice},
                timeout=160,
            )
        except Exception as exc:
            render_callout(f"PCA endpoint failed: {explain_api_error(exc)}", "danger")
        else:
            data = pca_payload.get("data", {})
            colors = [DANGER if label == 1 else ACCENT for label in data.get("labels", [])]
            fig = go.Figure(
                go.Scattergl(
                    x=data.get("x", []),
                    y=data.get("y", []),
                    mode="markers",
                    marker=dict(
                        color=colors,
                        size=5,
                        opacity=0.72,
                        line=dict(width=0),
                    ),
                    text=[f"score={format_number(score)}" for score in data.get("scores", [])],
                    name=data.get("model_used", model_choice),
                )
            )
            fig.update_layout(
                **PLOTLY_LAYOUT,
                height=520,
                xaxis_title=data.get("pc1_label", "PC1"),
                yaxis_title=data.get("pc2_label", "PC2"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
