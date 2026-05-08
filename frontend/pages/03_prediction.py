"""Single-connection prediction page."""

from __future__ import annotations

import os
import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (  # noqa: E402
    ACCENT,
    DANGER,
    PAGE_CONFIG,
    PLOTLY_LAYOUT,
    SUCCESS,
    VIOLET,
    WARNING,
    api_get,
    api_post,
    explain_api_error,
    format_number,
    render_app_shell,
    render_callout,
    render_kv_panel,
    render_metric_cards,
    render_page_header,
    render_score_bars,
)


PREDICTION_DEFAULTS = {
    "dur": 0.5,
    "rate": 20.0,
    "sbytes": 1500,
    "dbytes": 5000,
    "spkts": 10,
    "dpkts": 15,
    "sttl": 64,
    "dttl": 64,
    "sload": 0.0,
    "dload": 0.0,
}

PRESETS = {
    "Normal web flow": {
        **PREDICTION_DEFAULTS,
        "sbytes": 1800,
        "dbytes": 6200,
        "spkts": 12,
        "dpkts": 18,
        "rate": 24.0,
    },
    "Port scan": {
        **PREDICTION_DEFAULTS,
        "dur": 0.001,
        "rate": 1200.0,
        "sbytes": 60,
        "dbytes": 0,
        "spkts": 1,
        "dpkts": 0,
        "sload": 14000.0,
        "sttl": 255,
        "dttl": 0,
    },
    "Volumetric burst": {
        **PREDICTION_DEFAULTS,
        "dur": 4.2,
        "rate": 10000.0,
        "sbytes": 500000,
        "dbytes": 0,
        "spkts": 6000,
        "dpkts": 0,
        "sload": 4000000.0,
        "dload": 0.0,
        "sttl": 255,
        "dttl": 0,
    },
}


def init_state() -> None:
    if st.session_state.get("_prediction_ready"):
        return
    st.session_state.selected_preset = "Normal web flow"
    st.session_state.applied_preset = None
    st.session_state.prediction_result = None
    st.session_state.prediction_error = None
    for field, value in PREDICTION_DEFAULTS.items():
        st.session_state[f"prediction_{field}"] = value
    st.session_state._prediction_ready = True


def apply_preset(name: str) -> None:
    if st.session_state.applied_preset == name:
        return
    for field, value in PRESETS[name].items():
        st.session_state[f"prediction_{field}"] = value
    st.session_state.applied_preset = name


def read_payload() -> dict:
    integers = {"sbytes", "dbytes", "spkts", "dpkts", "sttl", "dttl"}
    payload = {}
    for field in PREDICTION_DEFAULTS:
        value = st.session_state[f"prediction_{field}"]
        payload[field] = int(value) if field in integers else float(value)
    return payload


st.set_page_config(**PAGE_CONFIG)
render_app_shell("prediction")
init_state()

try:
    info = api_get("/api/predict/best_model", timeout=12)
except Exception as exc:
    info = {}
    render_callout(f"Prediction metadata unavailable: {explain_api_error(exc)}", "warning")

best_model = info.get("best_model", {})
metrics = best_model.get("metrics", {})

render_page_header(
    "Real-Time Prediction",
    "Connection scoring",
    "Raw network fields are rebuilt into the 20-feature model vector and scored against the deployed ensemble.",
    [
        best_model.get("name", "Model unavailable"),
        best_model.get("threshold", "threshold pending"),
    ],
)

render_metric_cards(
    [
        {
            "label": "F1",
            "value": format_number(metrics.get("f1")),
            "sub": "deployed model",
            "tone": "success",
        },
        {
            "label": "ROC-AUC",
            "value": format_number(metrics.get("roc_auc")),
            "sub": "test-set separation",
            "tone": "accent",
        },
        {
            "label": "Precision",
            "value": format_number(metrics.get("precision")),
            "sub": "alert quality",
        },
        {
            "label": "Recall",
            "value": format_number(metrics.get("recall")),
            "sub": "attack coverage",
        },
    ]
)

form_col, result_col = st.columns([1.05, 0.95], gap="large")

with form_col:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">Input</div>
            <div class="panel-heading">Network connection</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    preset = st.selectbox("Preset", list(PRESETS.keys()), key="selected_preset")
    apply_preset(preset)

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.number_input("Source bytes", min_value=0, step=100, key="prediction_sbytes")
        st.number_input("Source packets", min_value=0, step=1, key="prediction_spkts")
        st.number_input("Duration", min_value=0.0, step=0.1, key="prediction_dur")
        st.number_input("Source load", min_value=0.0, step=100.0, key="prediction_sload")
        st.number_input("Source TTL", min_value=0, max_value=255, step=1, key="prediction_sttl")
    with c2:
        st.number_input("Destination bytes", min_value=0, step=100, key="prediction_dbytes")
        st.number_input("Destination packets", min_value=0, step=1, key="prediction_dpkts")
        st.number_input("Rate", min_value=0.0, step=1.0, key="prediction_rate")
        st.number_input("Destination load", min_value=0.0, step=100.0, key="prediction_dload")
        st.number_input("Destination TTL", min_value=0, max_value=255, step=1, key="prediction_dttl")

    if st.button("Run prediction", use_container_width=True, type="primary"):
        try:
            st.session_state.prediction_result = api_post("/api/predict/single", read_payload(), timeout=90)
            st.session_state.prediction_error = None
        except Exception as exc:
            st.session_state.prediction_error = explain_api_error(exc)
            st.session_state.prediction_result = None

with result_col:
    result = st.session_state.prediction_result
    error = st.session_state.prediction_error
    if error:
        render_callout(f"Prediction failed: {error}", "danger")
    elif result:
        pred = result.get("prediction", {})
        is_anomaly = pred.get("label") == 1
        tone = "danger" if is_anomaly else "success"
        title_class = "danger" if is_anomaly else "success"
        st.markdown(
            f"""
            <div class="result {tone}">
                <div class="result-kicker">Prediction</div>
                <div class="result-title {title_class}">{pred.get("class_name", "-")}</div>
                <div class="result-meta">Risk {pred.get("risk_level", "-")} | Score {format_number(result.get("score"), 6)} | Threshold {format_number(result.get("threshold"), 6)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=float(result.get("score", 0.0)),
                number={"font": {"color": "#e5edf7"}},
                gauge={
                    "axis": {"range": [0, 1], "tickcolor": "#94a3b8"},
                    "bar": {"color": DANGER if is_anomaly else SUCCESS},
                    "bgcolor": "#0f1724",
                    "bordercolor": "#243244",
                    "steps": [
                        {"range": [0, min(float(result.get("threshold", 0.5)), 1)], "color": "#10251d"},
                        {"range": [min(float(result.get("threshold", 0.5)), 1), 1], "color": "#2b1520"},
                    ],
                    "threshold": {
                        "line": {"color": WARNING, "width": 3},
                        "thickness": 0.75,
                        "value": float(result.get("threshold", 0.5)),
                    },
                },
            )
        )
        gauge_layout = {key: value for key, value in PLOTLY_LAYOUT.items() if key != "margin"}
        gauge.update_layout(**gauge_layout, height=260, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(gauge, use_container_width=True)

        render_score_bars(
            {
                "IF": result.get("components", {}).get("if", 0.0),
                "LOF": result.get("components", {}).get("lof", 0.0),
                "AE": result.get("components", {}).get("ae", 0.0),
                "Final": result.get("components", {}).get("final", 0.0),
            },
            {"IF": ACCENT, "LOF": VIOLET, "AE": WARNING, "Final": DANGER if is_anomaly else SUCCESS},
        )

        inferred = result.get("inferred_raw", {})
        if inferred:
            render_kv_panel(
                "Inferred raw fields",
                "Nearest-neighbor estimates",
                [(key, format_number(value)) for key, value in inferred.items()],
            )
    else:
        render_kv_panel(
            "Deployment",
            best_model.get("name", "Model unavailable"),
            [
                ("Threshold", best_model.get("threshold", "-")),
                ("Contamination", format_number(best_model.get("contamination"))),
                ("Components", len(best_model.get("components", []))),
                ("Backend", os.getenv("BACKEND_URL", "http://localhost:5000")),
            ],
        )
