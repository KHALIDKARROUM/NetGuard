"""Explore benchmark records, class balance, and physical features."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    PAGE_CONFIG, panel, api_get, explain_api_error,
    format_number, format_percent, render_app_shell, render_callout, render_empty_state,
    render_footer, render_kv_panel, render_metric_cards, render_page_header, render_section_header, render_tags,
)
from charts import distribution_chart, show_chart, traffic_donut
from file_security import safe_csv

st.set_page_config(**PAGE_CONFIG)
render_app_shell("dataset")
render_page_header("Dataset explorer", "KNOW YOUR TRAFFIC", "Explore labeled connections and the physical features behind every prediction.")
try:
    with st.spinner("Loading the dataset…"):
        info = api_get("/api/dataset/info", timeout=20)
except Exception as exc:
    render_callout(explain_api_error(exc), "warning")
    render_empty_state("The dataset is unavailable", "Start the analysis service and select Refresh data to continue.", "database")
    render_footer()
    st.stop()

overview = info.get("overview", {})
test = overview.get("test_set", {})
train = overview.get("train_set", {})
features = overview.get("feature_names", [])
render_metric_cards([
    dict(label="Training connections", value=format_number(train.get("n_rows"), 0), sub="Training dataset", icon="database"),
    dict(label="Benchmark connections", value=format_number(test.get("n_rows"), 0), sub="Previously inspected evaluation set", icon="layers", tone="violet"),
    dict(label="Physical features", value=format_number(test.get("n_features"), 0), sub="Raw measurements + derived features", icon="activity"),
    dict(label="Anomaly share", value=format_percent(test.get("anomaly_rate")), sub=f"{test.get('n_anomalies', 0):,} labeled anomalies", icon="target", tone="danger"),
])

view = st.radio("Explore dataset", ["Traffic profile", "Browse records", "Feature distributions", "Feature statistics"], horizontal=True, label_visibility="collapsed", key="dataset_view")
if view == "Traffic profile":
    left, right = st.columns([1.1, 1], gap="medium")
    pie = info.get("label_distribution", {}).get("pie_chart", {})
    with left, panel():
        render_section_header("Class balance", "Normal traffic and labeled anomalies")
        if pie and sum(pie.get("values", [])):
            show_chart(traffic_donut(pie["labels"], pie["values"], height=330))
            st.caption(f"Normal: {test.get('n_normal', 0):,} · Anomaly: {test.get('n_anomalies', 0):,}")
        else:
            render_empty_state("No class data", "Class labels were not returned for this dataset.", "database")
    with right:
        render_kv_panel("DATA SOURCE", "UNSW-NB15 benchmark", [
            ("Source", info.get("source_file", "—")), ("Connections", format_number(test.get("n_rows"), 0)),
            ("Features", len(features)), ("Representation", "Physical features before scaling"), ("Evaluation", "Previously inspected benchmark"),
        ])
        with panel():
            render_section_header("Feature inventory", "Measurements and derived inputs used by the model")
            render_tags(features)
    render_callout("These are recorded benchmark connections. Model and threshold selection use validation data; this dataset is not an untouched final holdout.")

elif view == "Browse records":
    with panel():
        render_section_header("Connection records", "Preview the first rows of the benchmark. Filters apply to this preview.", "EXPORTABLE")
        c1, c2 = st.columns([1, 1])
        with c1:
            n = st.selectbox("Preview size", [50, 100, 250, 500], index=1, format_func=lambda v: f"{v} connections")
        with c2:
            class_filter = st.selectbox("Traffic class", ["All traffic", "Normal", "Anomaly"])
        try:
            sample = pd.DataFrame(api_get("/api/dataset/sample", params={"n": n}, timeout=20).get("sample", []))
        except Exception as exc:
            render_callout(explain_api_error(exc), "danger")
        else:
            if class_filter != "All traffic" and "label" in sample:
                sample = sample[sample.label == (1 if class_filter == "Anomaly" else 0)]
            default = [c for c in ["label", "sbytes", "dbytes", "spkts", "dpkts", "dur", "rate", "sttl", "dttl"] if c in sample]
            columns = st.multiselect("Visible columns", list(sample.columns), default=default or list(sample.columns)[:8])
            if sample.empty:
                render_empty_state("No matching connections", "Try another traffic class or increase the preview size.", "database")
            elif not columns:
                render_callout("Select at least one column to view records.")
            else:
                st.dataframe(sample[columns], use_container_width=True, hide_index=True, height=380)
                st.caption(f"Showing {len(sample):,} of {n} preview records · label 0 = normal, 1 = anomaly")
                st.download_button("Download filtered records", safe_csv(sample[columns]), "netguard_records.csv", "text/csv")

elif view == "Feature distributions":
    try:
        with st.spinner("Loading feature distributions…"):
            distributions = api_get("/api/dataset/distributions", params={"top_n": 20}, timeout=30).get("distributions", {})
    except Exception as exc:
        render_callout(explain_api_error(exc), "danger")
    else:
        if not distributions:
            render_empty_state("No distributions available", "The service returned no feature distributions.")
        else:
            with panel():
                render_section_header("Compare traffic patterns", "Sampled distributions; summary statistics use the full class.")
                feature = st.selectbox("Physical feature", list(distributions))
                payload = distributions[feature]
                show_chart(distribution_chart(payload.get("normal", []), payload.get("anomaly", []), feature))
            normal, anomaly = st.columns(2)
            for col, title, key in [(normal, "Normal traffic", "stats_normal"), (anomaly, "Anomaly traffic", "stats_anomaly")]:
                with col:
                    render_kv_panel("CLASS STATISTICS", title, [(k.upper(), format_number(v, 4)) for k, v in payload.get(key, {}).items()])

else:
    with panel():
        render_section_header("Feature statistics", "Physical feature values before training-fitted standardization")
        query = st.text_input("Find a feature", placeholder="Search by feature name…")
        stats = pd.DataFrame(overview.get("numeric_stats", {})).T
        if not stats.empty:
            stats = stats.rename_axis("Feature").reset_index()
            stats = stats[stats.Feature.str.contains(query, case=False, regex=False)]
            if stats.empty:
                render_empty_state("No matching features", "Try a shorter feature name.")
            else:
                st.dataframe(stats, use_container_width=True, hide_index=True, height=440)
                st.download_button("Download feature statistics", safe_csv(stats), "netguard_feature_statistics.csv", "text/csv")
        else:
            render_empty_state("Statistics unavailable", "No numeric statistics were returned by the service.")
render_footer()
