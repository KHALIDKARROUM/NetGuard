"""The NetGuard workspace overview."""
from __future__ import annotations
import sys
from pathlib import Path
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    PAGE_CONFIG, panel, api_get, explain_api_error, format_number, format_percent, format_rate,
    render_app_shell, render_callout, render_empty_state, render_footer, render_hero,
    render_metric_cards, render_page_header, render_score_bars, render_section_header,
)
from charts import show_chart, traffic_donut

st.set_page_config(**PAGE_CONFIG)
health = render_app_shell("home")
render_page_header("Workspace overview", "YOUR NETWORK, AT A GLANCE", "A single place to explore traffic and understand your detection model.")
render_hero()

dataset = model_info = {}
errors = []
with st.spinner("Loading workspace insights…"):
    for label, path in [("Dataset", "/api/dataset/info"), ("Model", "/api/predict/best_model")]:
        try:
            payload = api_get(path, timeout=15)
            if label == "Dataset":
                dataset = payload
            else:
                model_info = payload
        except Exception as exc:
            errors.append((label, explain_api_error(exc)))
if errors:
    render_callout("Some insights are unavailable. You can still navigate the workspace.", "warning")
    with st.expander("View service details"):
        for label, message in errors:
            st.caption(f"{label}: {message}")

overview = dataset.get("overview", {})
train = overview.get("train_set", {})
test = overview.get("test_set", {})
model = model_info.get("best_model", {})
metrics = model.get("metrics", {})
render_metric_cards([
    dict(label="Training connections", value=format_number(train.get("n_rows"), 0), sub="UNSW-NB15 training set", icon="database"),
    dict(label="Benchmark connections", value=format_number(test.get("n_rows"), 0), sub=f"{format_percent(test.get('anomaly_rate'))} labeled anomalies" if test else "Dataset unavailable", icon="layers", tone="violet"),
    dict(label="Detection F1", value=format_number(metrics.get("f1")), sub="Previously inspected benchmark · 0–1", icon="shield"),
    dict(label="Attack recall", value=format_rate(metrics.get("recall")), sub="Share of benchmark attacks detected", icon="target"),
])

left, right = st.columns([1.1, 1], gap="medium")
with left, panel():
    render_section_header("Traffic composition", "Labeled connections in the benchmark dataset", "UNSW-NB15")
    pie = dataset.get("label_distribution", {}).get("pie_chart", {})
    if pie and sum(pie.get("values", [])):
        show_chart(traffic_donut(pie["labels"], pie["values"]))
        normal, anomaly = st.columns(2)
        with normal:
            render_callout(f"Normal traffic · {pie['values'][0]:,}", "success")
        with anomaly:
            render_callout(f"Anomaly traffic · {pie['values'][1]:,}", "danger")
    else:
        render_empty_state("Traffic insights unavailable", "Connect the analysis service to view the dataset profile.", "database")
with right, panel():
    render_section_header("Detection quality", "The saved model's benchmark operating point", "DEPLOYED MODEL")
    if model:
        st.markdown(f"**{model.get('name', 'Current model')}**")
        render_score_bars({"Precision": metrics.get("precision", 0), "Recall": metrics.get("recall", 0), "F1 score": metrics.get("f1", 0), "ROC-AUC": metrics.get("roc_auc", 0)})
        st.caption(f"Decision threshold: {format_number(model.get('threshold'), 6)} · False alarms: {format_rate(metrics.get('false_positive_rate'), 2)}")
        render_callout("Selected on validation data. Benchmark results describe previously inspected traffic.")
        st.page_link("pages/02_performance.py", label="Explore model performance", icon=":material/arrow_forward:")
    else:
        render_empty_state("Model insights unavailable", "Load the saved model to see its detection quality.", "shield")

render_section_header("Continue your analysis", "Choose a starting point for your next investigation.")
for col, title, copy, path, label, material_icon in zip(
    st.columns(3, gap="medium"),
    ["Explore the dataset", "Evaluate detection", "Investigate a connection"],
    ["Inspect traffic classes, feature distributions, and individual records.", "Compare validation candidates and understand model behavior.", "Score one connection or a CSV batch with the deployed model."],
    ["pages/01_dataset.py", "pages/02_performance.py", "pages/03_prediction.py"],
    ["Open dataset explorer", "View performance", "Open prediction lab"],
    [":material/database:", ":material/monitoring:", ":material/radar:"],
):
    with col, panel():
        render_section_header(title, copy)
        st.page_link(path, label=label, icon=material_icon)
render_footer()
