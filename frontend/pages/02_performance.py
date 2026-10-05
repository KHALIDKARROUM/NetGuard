"""Focused, on-demand analysis of validation candidates and benchmark behavior."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    ACCENT, DANGER, PAGE_CONFIG, panel, PALETTE, PLOTLY_LAYOUT, SUCCESS, api_get, explain_api_error,
    format_number, format_rate, render_app_shell, render_callout, render_empty_state,
    render_footer, render_kv_panel, render_metric_cards, render_page_header, render_section_header,
)
from charts import distribution_chart, show_chart
from file_security import safe_csv

st.set_page_config(**PAGE_CONFIG)
render_app_shell("performance")
render_page_header("Model performance", "MEASURE WHAT MATTERS", "Compare validation candidates and inspect how the deployed model handles benchmark traffic.")
try:
    with st.spinner("Loading model evaluation… The first evaluation may take a moment."):
        compare = api_get("/api/models/compare", timeout=90)
except Exception as exc:
    render_callout(explain_api_error(exc), "warning")
    render_empty_state("Evaluation unavailable", "Load the saved model and dataset, then select Refresh data.", "shield")
    render_footer()
    st.stop()
metrics = compare.get("metrics", [])
if not metrics:
    render_empty_state("No evaluation results", "No model metrics were returned by the service.", "shield")
    render_footer()
    st.stop()
best = next((m for m in metrics if m.get("model") == compare.get("best_model")), metrics[0])
render_metric_cards([
    dict(label="F1 score", value=format_number(best.get("f1")), sub="Precision and recall balance · 0–1", icon="shield"),
    dict(label="ROC-AUC", value=format_number(best.get("roc_auc")), sub="Class separation · 0–1", icon="activity", tone="violet"),
    dict(label="Attack recall", value=format_rate(best.get("recall")), sub="Benchmark attacks detected", icon="target"),
    dict(label="False-alarm rate", value=format_rate(best.get("false_positive_rate"), 2), sub="Normal benchmark traffic flagged", icon="activity", tone="danger"),
])
render_callout("The model and threshold were frozen using validation data. The benchmark was previously inspected; independent final testing is still needed.")

view = st.radio("Analysis view", ["Validation comparison", "ROC curve", "Confusion matrix", "Score distribution", "Feature projection"], horizontal=True, label_visibility="collapsed", key="performance_view")
if view == "Validation comparison":
    validation = pd.DataFrame(compare.get("validation_comparison", []))
    if validation.empty:
        render_empty_state("No validation comparison", "Run the notebook workflow to generate candidate results.", "layers")
    else:
        left, right = st.columns([1.5, 1], gap="medium")
        with left, panel():
            render_section_header("Candidate detection coverage", "Attack recall under each candidate's validation false-alarm budget", "VALIDATION")
            if "recall" in validation and "model" in validation:
                chart = validation.sort_values("recall")
                colors = [ACCENT if bool(row.get("selected", False)) else "#b6c7d1" for row in chart.to_dict("records")]
                fig = go.Figure(go.Bar(x=chart.recall * 100, y=chart.model, orientation="h", marker_color=colors,
                    text=[f"{v:.1%}" for v in chart.recall], textposition="outside", cliponaxis=False,
                    hovertemplate="%{y}<br>Attack recall: %{x:.1f}%<extra></extra>"))
                fig.update_layout(**PLOTLY_LAYOUT, height=300, xaxis_title="Attack recall (%)", showlegend=False)
                fig.update_xaxes(range=[0, 110])
                show_chart(fig)
            st.caption("Teal marks the validation-selected candidate. All candidates use the same grouped split and fit-only preprocessing.")
        with right:
            render_kv_panel("DEPLOYED MODEL", best.get("model", "Current model"), [
                ("Selection", "Grouped validation"), ("Precision", format_rate(best.get("precision"))),
                ("Recall", format_rate(best.get("recall"))), ("F1", format_number(best.get("f1"))),
                ("Benchmark inference", f"{format_number(best.get('inference_s'))} s"),
            ])
            decision = compare.get("ensemble_decision", {})
            if decision:
                render_callout(f"Ensemble {'retained' if decision.get('retained') else 'rejected'} under the declared validation gain and prediction-time rules.")
        with panel():
            render_section_header("Validation comparison", "Detection quality at a maximum 1% validation false-alarm budget")
            cols = [c for c in ["model", "selected", "recall", "precision", "f1", "false_positive_rate", "single_latency_median_ms"] if c in validation]
            table = validation[cols].copy()
            for c in ["recall", "precision", "false_positive_rate"]:
                if c in table:
                    table[c] = table[c].map(lambda v: format_rate(v, 2))
            table = table.rename(columns={"model":"Candidate", "selected":"Selected", "recall":"Recall", "precision":"Precision", "f1":"F1", "false_positive_rate":"False alarms", "single_latency_median_ms":"Single latency (ms)"})
            st.dataframe(table, use_container_width=True, hide_index=True, column_config={
                "F1":st.column_config.NumberColumn(format="%.3f"),
                "Single latency (ms)":st.column_config.NumberColumn(format="%.2f"),
            })
            with st.expander("Detailed validation results and timing"):
                st.caption("Timing includes raw feature creation, scaling, scoring, and the decision. Network time is excluded.")
                st.dataframe(validation, use_container_width=True, hide_index=True)
            st.download_button("Download validation comparison", safe_csv(validation), "netguard_validation.csv", "text/csv")
else:
    kind = {"ROC curve":"roc", "Confusion matrix":"confusion", "Score distribution":"scores", "Feature projection":"pca"}[view]
    try:
        with st.spinner(f"Loading {view.lower()}…"):
            payload = api_get("/api/models/viz", params={"type": kind}, timeout=160).get("data")
    except Exception as exc:
        render_callout(explain_api_error(exc), "danger")
    else:
        if not payload:
            render_empty_state("No chart data", "The service returned no results for this analysis.")
        elif kind == "roc":
            with panel():
                render_section_header("Detection across thresholds", "A curve closer to the upper-left corner separates the two classes better.", "BENCHMARK")
                fig = go.Figure(go.Scatter(x=[0,1], y=[0,1], mode="lines", name="Random baseline", line=dict(color="#c2ccd5", dash="dash", width=1.5)))
                for i, (name, curve) in enumerate(payload.items()):
                    fig.add_trace(go.Scatter(x=curve.get("fpr", []), y=curve.get("tpr", []), mode="lines", name=name, line=dict(color=PALETTE[i % len(PALETTE)], width=3)))
                fig.update_layout(**PLOTLY_LAYOUT, height=430, xaxis_title="False-positive rate", yaxis_title="True-positive rate")
                show_chart(fig)
        elif kind == "confusion":
            with panel():
                render_section_header("Where predictions agree", "Rows are recorded classes; columns are predicted classes.", "BENCHMARK")
                names = [m.get("model_name", "Model") for m in payload]
                chosen = st.selectbox("Evaluated model", names)
                matrix = payload[names.index(chosen)]
                fig = go.Figure(go.Heatmap(z=matrix["z"], x=["Predicted normal", "Predicted anomaly"], y=["Actual normal", "Actual anomaly"],
                    colorscale=[[0,"#eef6f4"],[.5,"#75bbae"],[1,"#126e64"]], text=[[f"{v:,}" for v in row] for row in matrix["z"]],
                    texttemplate="%{text}", textfont=dict(size=22), showscale=False, xgap=8, ygap=8,
                    hovertemplate="%{y}<br>%{x}<br>%{z:,} connections<extra></extra>"))
                fig.update_layout(**PLOTLY_LAYOUT, height=370)
                fig.update_yaxes(autorange="reversed")
                show_chart(fig)
        elif kind == "scores":
            with panel():
                render_section_header("How the model scores traffic", "Compare the score distributions for recorded normal and anomaly classes.", "BENCHMARK")
                chosen = st.selectbox("Evaluated model", list(payload))
                data = payload[chosen]
                show_chart(distribution_chart(data.get("normal", []), data.get("anomaly", []), "Model score", 400))
                render_callout("Model scores are not calibrated production attack probabilities.")
                with st.expander("Score percentiles"):
                    st.dataframe(pd.DataFrame([data.get("percentiles", {})]), use_container_width=True, hide_index=True)
        else:
            with panel():
                render_section_header("Traffic in feature space", "A two-dimensional PCA view of training-scaled features. Color shows the model's prediction.", "DESCRIPTIVE")
                fig = go.Figure()
                for label, name, color in [(0,"Predicted normal",SUCCESS),(1,"Predicted anomaly",DANGER)]:
                    indices = [i for i, v in enumerate(payload.get("labels", [])) if v == label]
                    fig.add_trace(go.Scattergl(x=[payload["x"][i] for i in indices], y=[payload["y"][i] for i in indices], mode="markers", name=name,
                        marker=dict(color=color, size=5, opacity=.5), text=[f"Score {format_number(payload['scores'][i])}" for i in indices], hovertemplate="%{text}<extra>%{fullData.name}</extra>"))
                fig.update_layout(**PLOTLY_LAYOUT, height=450, xaxis_title=payload.get("pc1_label", "PC1"), yaxis_title=payload.get("pc2_label", "PC2"))
                show_chart(fig)
with st.expander("Deployed model · full benchmark metrics"):
    columns = [c for c in ["model", "accuracy", "roc_auc", "f1", "recall", "precision", "false_positive_rate", "inference_s"] if c in best]
    st.dataframe(pd.DataFrame(metrics)[columns], use_container_width=True, hide_index=True)
render_footer()
