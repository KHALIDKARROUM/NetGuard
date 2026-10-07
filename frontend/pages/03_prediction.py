"""Connection and CSV batch scoring through the shared, frozen model."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    DANGER, PAGE_CONFIG, panel, PLOTLY_LAYOUT, SUCCESS, TEXT, WARNING, api_get, api_post,
    explain_api_error, format_number, format_rate, icon, render_app_shell,
    render_callout, render_empty_state, render_footer, render_kv_panel,
    render_page_header, render_section_header,
)
from charts import show_chart
from prediction_inputs import DEFAULTS, INTEGER_FIELDS, MAX_EXACT_COUNT, PRESETS, validate_connections
from file_security import read_connection_csv, safe_csv

def apply_preset() -> None:
    st.session_state._prediction_preset = st.session_state.prediction_preset
    st.session_state._prediction_measurements = PRESETS[st.session_state.prediction_preset].copy()
    for field, value in PRESETS[st.session_state.prediction_preset].items():
        st.session_state[f"prediction_{field}"] = value
    st.session_state.prediction_result = None
    st.session_state.prediction_error = None

def reset_model_results() -> None:
    for key in ("prediction_result", "prediction_error", "batch_result", "batch_error"):
        st.session_state[key] = None

def read_payload() -> dict:
    return {name: (int if name in INTEGER_FIELDS else float)(st.session_state[f"prediction_{name}"]) for name in DEFAULTS}

def input_field(field: str, label: str, help_text: str = "") -> None:
    integer = field in INTEGER_FIELDS
    options = dict(min_value=0 if integer else 0., step=1 if integer else .1, key=f"prediction_{field}", help=help_text or None)
    if integer:
        options["max_value"] = 255 if field in {"sttl", "dttl"} else MAX_EXACT_COUNT
    st.number_input(label, **options)

st.set_page_config(**PAGE_CONFIG)
render_app_shell("prediction")
render_page_header("Prediction lab", "FROM TRAFFIC TO A DECISION", "Investigate a single connection or score a CSV batch with the deployed detection model.")
if "prediction_result" not in st.session_state:
    st.session_state.prediction_result = None
    st.session_state.prediction_error = None
if "prediction_preset" not in st.session_state:
    st.session_state.prediction_preset = st.session_state.get("_prediction_preset", "Web traffic example")
for field, value in st.session_state.get("_prediction_measurements", DEFAULTS).items():
    if f"prediction_{field}" not in st.session_state:
        st.session_state[f"prediction_{field}"] = value

try:
    info = api_get("/api/predict/best_model", timeout=15)
except Exception as exc:
    info = {}
    render_callout(explain_api_error(exc), "warning")
model = info.get("best_model", {})
available = info.get("available_models", [])
if available:
    choices = {item["id"]: item for item in available}
    default_id = next((item["id"] for item in available if item.get("default")), available[0]["id"])
    if st.session_state.get("prediction_model") not in choices:
        st.session_state.prediction_model = default_id
    selected_id = st.selectbox("Detection model", list(choices), key="prediction_model",
        format_func=lambda name: {"xgboost": "XGBoost (recommended)", "lightgbm": "LightGBM", "tabm": "TabM neural network"}.get(name, name),
        on_change=reset_model_results)
    model = choices[selected_id]
    prediction_query = "?" + urlencode({"model": selected_id})
else:
    prediction_query = ""
if model:
    st.caption(f"Deployed model: {model.get('name', '—')}  ·  Threshold: {format_number(model.get('threshold'), 6)}  ·  {model.get('feature_count', 29)} physical features")

mode = st.radio("Prediction mode", ["Single connection", "CSV batch"], horizontal=True, label_visibility="collapsed", key="prediction_mode")
if mode == "Single connection":
    form_col, result_col = st.columns([1.15, 1], gap="medium")
    with form_col, panel():
        render_section_header("Connection measurements", "Enter observed values or start with an illustrative example.", "01 · INPUT")
        st.selectbox("Start from an example", list(PRESETS), key="prediction_preset", on_change=apply_preset)
        st.caption("Examples illustrate input patterns; their names do not guarantee a prediction. Rate and load retain the collector's recorded units.")
        with st.form("connection_form", border=False):
            st.markdown('<div class="step-label">Traffic volume</div>', unsafe_allow_html=True)
            source, destination = st.columns(2)
            with source:
                input_field("sbytes", "Source bytes", "Recorded bytes sent from source to destination.")
                input_field("spkts", "Source packets")
            with destination:
                input_field("dbytes", "Destination bytes", "Recorded bytes sent from destination to source.")
                input_field("dpkts", "Destination packets")
            st.markdown('<div class="step-label">Timing & throughput</div>', unsafe_allow_html=True)
            source, destination = st.columns(2)
            with source:
                input_field("dur", "Duration (seconds)")
                input_field("sload", "Source load", "Use the measured source load in the collector's original units.")
            with destination:
                input_field("rate", "Recorded rate", "Use the measured rate; it is not recalculated from packets or duration.")
                input_field("dload", "Destination load", "Use the measured destination load in the collector's original units.")
            st.markdown('<div class="step-label">Packet lifetime</div>', unsafe_allow_html=True)
            source, destination = st.columns(2)
            with source:
                input_field("sttl", "Source TTL (0–255)")
            with destination:
                input_field("dttl", "Destination TTL (0–255)")
            submitted = st.form_submit_button("Analyze connection", type="primary", use_container_width=True, disabled=not bool(model))
        if submitted:
            st.session_state.prediction_result = None
            st.session_state.prediction_error = None
            try:
                connection = validate_connections(pd.DataFrame([read_payload()]))[0]
                st.session_state._prediction_measurements = connection.copy()
                with st.spinner("Analyzing connection…"):
                    st.session_state.prediction_result = api_post("/api/predict/single" + prediction_query, connection)
            except Exception as exc:
                st.session_state.prediction_error = explain_api_error(exc)
    with result_col, panel():
        render_section_header("Analysis result", "The last submitted connection's classification", "02 · RESULT")
        result = st.session_state.prediction_result
        error = st.session_state.prediction_error
        if error:
            render_callout(error, "danger")
            render_empty_state("Analysis could not complete", "Review the input values and try again.", "alert")
        elif result:
            anomaly = result.get("prediction", {}).get("label") == 1
            tone = "danger" if anomaly else "success"
            title = "Anomaly detected" if anomaly else "Normal connection"
            score = float(result.get("score", 0))
            threshold = float(result.get("threshold", .5))
            st.markdown(f'<div class="result {tone}"><div class="result-kicker">{icon("alert" if anomaly else "check", 17)} ANALYSIS COMPLETE</div><div class="result-title">{title}</div><div class="result-meta">{"The score meets or exceeds the saved decision threshold." if anomaly else "The score is below the saved decision threshold."}</div></div>', unsafe_allow_html=True)
            fig = go.Figure(go.Indicator(mode="gauge+number", value=score,
                number=dict(font=dict(color=TEXT, size=38), valueformat=".4f"),
                title=dict(text="MODEL SCORE", font=dict(color="#738294", size=10)),
                gauge=dict(axis=dict(range=[0,1], tickwidth=0, tickfont=dict(size=10)), bar=dict(color=DANGER if anomaly else SUCCESS, thickness=.45),
                    bgcolor="#fff", borderwidth=0,
                    steps=[dict(range=[0,threshold], color="#e3f2ea"), dict(range=[threshold,1], color="#fbe5df")],
                    threshold=dict(line=dict(color=WARNING, width=3), thickness=.85, value=threshold))))
            fig.update_layout(**PLOTLY_LAYOUT, height=250)
            show_chart(fig)
            render_kv_panel("DECISION DETAILS", "Saved operating point", [("Model score", format_number(score, 6)), ("Decision threshold", format_number(threshold, 6)), ("Model", result.get("model", "—"))])
            render_callout("The score is not calibrated as a production attack probability. A classification is a model decision, not a verified incident.")
            with st.expander("Measurements used for this result"):
                st.json(result.get("input", {}))
            st.download_button("Download analysis", json.dumps(result, indent=2, allow_nan=False), "netguard_prediction.json", "application/json")
        else:
            render_empty_state("Ready when you are", "Add connection measurements, then select Analyze connection to see the score and decision.", "shield")
            if model:
                render_kv_panel("MODEL CONTEXT", model.get("name", "Detection model"), [("Decision threshold", format_number(model.get("threshold"), 6)),
                    ("Validation false-alarm target", format_rate(model.get("threshold_selection", {}).get("max_false_positive_rate", .01))),
                    ("Model components", len(model.get("components", []))), ("Input measurements", len(DEFAULTS))])
else:
    left, right = st.columns([1.5, 1], gap="medium")
    connections = None
    file_key = None
    with left, panel():
        render_section_header("Score a batch", "Upload a CSV containing up to 1,000 measured connections.", "01 · UPLOAD")
        template = pd.DataFrame(list(PRESETS.values()))
        st.download_button("Download CSV template", safe_csv(template), "netguard_batch_template.csv", "text/csv")
        upload = st.file_uploader("Connection measurements", type=["csv"], help="Ten required measurement columns. Maximum 1,000 rows and 2 MB.")
        st.caption("NetGuard processes uploads for this session and does not save a copy of the uploaded file.")
        if upload is not None:
            raw = upload.getvalue()
            file_key = hashlib.sha256(raw).hexdigest()
            if st.session_state.get("batch_file_key") != file_key:
                st.session_state.batch_file_key = file_key
                st.session_state.batch_result = None
                st.session_state.batch_error = None
            try:
                frame = read_connection_csv(raw)
                connections = validate_connections(frame)
                render_callout(f"{len(connections):,} connections validated and ready to analyze.", "success")
                if extra := [c for c in frame if c not in DEFAULTS]:
                    st.caption("Only the ten required measurements are scored. Extra columns are ignored: " + ", ".join(extra))
                st.dataframe(pd.DataFrame(connections).head(8), use_container_width=True, hide_index=True)
            except Exception as exc:
                render_callout(str(exc), "danger")
        if st.button("Analyze batch", type="primary", use_container_width=True, disabled=not (model and connections)):
            st.session_state.batch_result = None
            st.session_state.batch_error = None
            try:
                with st.spinner("Analyzing batch…"):
                    st.session_state.batch_result = api_post("/api/predict/batch" + prediction_query, {"connections": connections}, timeout=120)
            except Exception as exc:
                st.session_state.batch_error = explain_api_error(exc)
    with right:
        render_kv_panel("CSV REQUIREMENTS", "Measured inputs, one row per connection", [("Connections", "1–1,000"), ("Size", "Up to 2 MB"), ("Counts", "Whole numbers, ≥ 0"), ("TTL", "Whole numbers, 0–255"), ("Rate & load", "Recorded collector units"), ("Missing values", "Not accepted")])
        with st.expander("Required CSV headers", expanded=True):
            st.code(",".join(DEFAULTS), language=None)
        render_callout("Use recorded measurements. The examples in the template are illustrative and do not guarantee a class.")
    if file_key and connections:
        if st.session_state.get("batch_error"):
            render_callout(st.session_state.batch_error, "danger")
        if batch := st.session_state.get("batch_result"):
            rows = [{"Row": i, "Model": p.get("model", ""), "Classification": p["prediction"]["class_name"], "Model score": p["score"], "Threshold": p["threshold"], **p.get("input", {})} for i,p in enumerate(batch.get("predictions", []), start=1)]
            results = pd.DataFrame(rows)
            with panel():
                anomalies = sum(p["prediction"]["label"] == 1 for p in batch.get("predictions", []))
                render_section_header("Batch results", f"{len(rows):,} connections analyzed · {anomalies:,} flagged anomalies", "02 · RESULTS")
                st.dataframe(results, use_container_width=True, hide_index=True)
                st.download_button("Download batch results", safe_csv(results), "netguard_batch_results.csv", "text/csv")
                render_callout("Model scores are not calibrated production attack probabilities.")
render_footer()
