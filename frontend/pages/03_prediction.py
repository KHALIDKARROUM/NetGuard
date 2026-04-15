"""
Prediction page for single-connection inference.
"""

import os
import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (  # noqa: E402
    ACCENT,
    DANGER,
    PAGE_CONFIG,
    SUCCESS,
    WARNING,
    api_post,
    api_get,
    explain_api_error,
    format_number,
    render_app_shell,
    render_metric_cards,
    render_page_header,
)

PREDICTION_DEFAULTS = {
    "dur": 0.5,
    "rate": 20.0,
    "sbytes": 1000,
    "dbytes": 800,
    "spkts": 10,
    "dpkts": 8,
    "sttl": 64,
    "dttl": 64,
    "sload": 0.0,
    "dload": 0.0,
}

PRESETS = {
    "Profil normal": {
        **PREDICTION_DEFAULTS,
        "sbytes": 1500,
        "dbytes": 5000,
        "spkts": 10,
        "dpkts": 15,
    },
    "Scan de ports": {
        **PREDICTION_DEFAULTS,
        "dur": 0.001,
        "rate": 1000.0,
        "sbytes": 50,
        "dbytes": 0,
        "spkts": 1,
        "dpkts": 0,
        "sload": 12000.0,
        "sttl": 255,
        "dttl": 0,
    },
    "Attaque volumetrique": {
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


def bootstrap_form_state() -> None:
    if "_prediction_state_ready" in st.session_state:
        return

    st.session_state.selected_prediction_preset = "Profil normal"
    st.session_state._applied_prediction_preset = None
    st.session_state.prediction_result = None
    st.session_state.prediction_error = None

    for field_name, value in PREDICTION_DEFAULTS.items():
        st.session_state[f"prediction_{field_name}"] = value

    st.session_state._prediction_state_ready = True


def apply_preset(preset_name: str) -> None:
    if st.session_state.get("_applied_prediction_preset") == preset_name:
        return

    for field_name, value in PRESETS[preset_name].items():
        st.session_state[f"prediction_{field_name}"] = value

    st.session_state._applied_prediction_preset = preset_name


def read_payload() -> dict:
    integer_fields = {
        "sbytes",
        "dbytes",
        "spkts",
        "dpkts",
        "sttl",
        "dttl",
    }

    payload = {}
    for field_name in PREDICTION_DEFAULTS:
        value = st.session_state[f"prediction_{field_name}"]
        payload[field_name] = int(value) if field_name in integer_fields else float(value)
    return payload


st.set_page_config(**PAGE_CONFIG)
render_app_shell("prediction")
bootstrap_form_state()

model_info = None
model_info_error = None
try:
    model_info = api_get("/api/predict/best_model", timeout=10)
except Exception as exc:
    model_info_error = explain_api_error(exc)
    model_info = None

best_model = model_info.get("best_model", {}) if model_info else {}
best_metrics = best_model.get("metrics", {})
component_list = best_model.get("components", [])
threshold_label = best_model.get("threshold", "Seuil backend non disponible")

render_page_header(
    "Inference temps reel",
    "Analyser une connexion reseau avec uniquement les variables qui changent vraiment la prediction.",
    (
        "Le formulaire a ete reduit aux variables reseau utiles. Le backend reconstruit "
        "les features derivees du modele a partir de ces champs puis compare le resultat "
        "au jeu de reference pour retourner une prediction stable."
    ),
    [
        best_model.get("name", "Modele deploye"),
        threshold_label,
    ],
)

if best_metrics:
    render_metric_cards(
        [
            {
                "label": "F1-score",
                "value": format_number(best_metrics.get("f1_score")),
                "sub": "modele deploye",
                "tone": "success",
            },
            {
                "label": "ROC-AUC",
                "value": format_number(best_metrics.get("roc_auc")),
                "sub": "separation globale",
                "tone": "accent",
            },
            {
                "label": "Precision",
                "value": format_number(best_metrics.get("precision")),
                "sub": "qualite des alertes",
            },
            {
                "label": "Score composite",
                "value": format_number(best_metrics.get("perf_score")),
                "sub": best_model.get("name", ""),
                "tone": "accent",
            },
        ]
    )

if model_info_error:
    st.markdown(
        f"""
        <div class="callout warn">
            Les informations du modele n'ont pas pu etre chargees.<br>
            Detail : {model_info_error}
        </div>
        """,
        unsafe_allow_html=True,
    )

if best_model:
    component_rows = "".join(
        f'<div class="stat-line">'
        f'<span class="stat-key">{component.get("name", "")}</span>'
        f'<span class="stat-value">{component.get("weight", 0):.1f}</span>'
        f'</div>'
        for component in component_list
    )
    st.markdown(
        f"""
        <div class="callout info">
            <strong>Modele deploye:</strong> {best_model.get("name", "")}<br>
            <strong>Decision:</strong> {best_model.get("decision_formula", "")}
        </div>
        <div class="panel">
            <div class="panel-title">Assemblage du modele</div>
            <div class="panel-heading">Poids retournes par l'API</div>
            <div class="stat-list">
                {component_rows}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

selected_preset = st.radio(
    "Preset de scenario",
    options=list(PRESETS.keys()),
    horizontal=True,
    key="selected_prediction_preset",
)
apply_preset(selected_preset)

preset_cards = st.columns(3, gap="large")
for column, (title, values) in zip(preset_cards, PRESETS.items()):
    with column:
        st.markdown(
            f"""
            <div class="quick-card">
                <div class="quick-card-title">{title}</div>
                <div class="quick-card-copy">
                    sbytes {values['sbytes']:,} | dbytes {values['dbytes']:,}<br>
                    spkts {values['spkts']} | dpkts {values['dpkts']}<br>
                    dur {values['dur']} | rate {values['rate']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

form_col, result_col = st.columns([1.3, 0.9], gap="large")

with form_col:
    with st.form("prediction_form", clear_on_submit=False):
        st.markdown('<div class="section-heading">Variables utiles</div>', unsafe_allow_html=True)

        st.markdown("##### Volume et debit")
        volume_cols = st.columns(4, gap="small")
        volume_cols[0].number_input("sbytes", min_value=0, key="prediction_sbytes", help="Bytes envoyes")
        volume_cols[1].number_input("dbytes", min_value=0, key="prediction_dbytes", help="Bytes recus")
        volume_cols[2].number_input("spkts", min_value=0, key="prediction_spkts", help="Paquets envoyes")
        volume_cols[3].number_input("dpkts", min_value=0, key="prediction_dpkts", help="Paquets recus")

        rate_cols = st.columns(4, gap="small")
        rate_cols[0].number_input("dur", min_value=0.0, format="%.4f", key="prediction_dur", help="Duree de la connexion")
        rate_cols[1].number_input("rate", min_value=0.0, format="%.2f", key="prediction_rate", help="Debit en paquets par seconde")
        rate_cols[2].number_input("sload", min_value=0.0, format="%.2f", key="prediction_sload", help="Charge source")
        rate_cols[3].number_input("dload", min_value=0.0, format="%.2f", key="prediction_dload", help="Charge destination")

        st.markdown("##### TTL reseau")
        tcp_cols = st.columns(2, gap="small")
        tcp_cols[0].number_input("sttl", min_value=0, max_value=255, key="prediction_sttl")
        tcp_cols[1].number_input("dttl", min_value=0, max_value=255, key="prediction_dttl")

        st.markdown(
            """
            <div class="helper-note">
                Les variables non exposees sont maintenues sur une valeur mediane du dataset
                de reference. Le backend recalcule ensuite les features derivees qui dependent
                du volume, des paquets, du debit et des TTL.
            </div>
            """,
            unsafe_allow_html=True,
        )

        submitted = st.form_submit_button(
            "Lancer l'analyse",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        try:
            st.session_state.prediction_result = api_post(
                "/api/predict/single",
                read_payload(),
                timeout=45,
            )
            st.session_state.prediction_error = None
        except Exception as exc:
            st.session_state.prediction_error = explain_api_error(exc)
            st.session_state.prediction_result = None

with result_col:
    prediction_error = st.session_state.get("prediction_error")
    prediction_result = st.session_state.get("prediction_result")

    if prediction_error:
        st.markdown(
            f"""
            <div class="callout danger">
                Impossible d'obtenir une prediction.<br>
                Detail : {prediction_error}
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif not prediction_result:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">Resultat</div>
                <div class="panel-heading">Soumettez le formulaire pour generer une prediction.</div>
                <p class="panel-copy">
                    Le panneau de droite affichera ensuite le score final, la jauge du seuil
                    backend et le detail de chaque composant de l'ensemble.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        prediction = prediction_result.get("prediction", 0)
        score = float(prediction_result.get("score", 0))
        threshold = float(prediction_result.get("threshold", 0.5))
        model_used = prediction_result.get("model_used", best_model.get("name", "Modele"))
        details = prediction_result.get("scores_detail", {})
        probabilities = prediction_result.get("probabilities", {})
        anomaly_pct = float(probabilities.get("anomaly", 0))
        normal_pct = float(probabilities.get("normal", 0))
        threshold_percentile = prediction_result.get("threshold_percentile")

        is_anomaly = prediction == 1
        banner_class = "danger" if is_anomaly else "success"
        banner_title = "Anomalie detectee" if is_anomaly else "Connexion normale"
        banner_copy = (
            f"Anomalie {anomaly_pct:.1f}% | Normal {normal_pct:.1f}% | score {score:.4f}"
        )

        st.markdown(
            f"""
            <div class="result-banner {banner_class}">
                <div class="result-tag">Prediction</div>
                <div class="result-title">{banner_title}</div>
                <div class="result-copy">{banner_copy}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        probability_markup = (
            f'<div class="score-row">'
            f'<div class="score-name">Anomalie</div>'
            f'<div class="score-weight">%</div>'
            f'<div class="score-track"><div class="score-fill" style="width:{anomaly_pct:.0f}%; background:{DANGER}"></div></div>'
            f'<div class="score-value" style="color:{DANGER}">{anomaly_pct:.1f}%</div>'
            f'</div>'
            f'<div class="score-row">'
            f'<div class="score-name">Normal</div>'
            f'<div class="score-weight">%</div>'
            f'<div class="score-track"><div class="score-fill" style="width:{normal_pct:.0f}%; background:{SUCCESS}"></div></div>'
            f'<div class="score-value" style="color:{SUCCESS}">{normal_pct:.1f}%</div>'
            f'</div>'
        )
        st.markdown(
            "<div class=\"panel\" style=\"margin-top:1rem\">"
            "<div class=\"panel-title\">Lecture du resultat</div>"
            "<div class=\"panel-heading\">Position de la connexion face au dataset de reference</div>"
            + probability_markup +
            "</div>",
            unsafe_allow_html=True,
        )

        weight_map = details.get("weights", {})
        component_scores = [
            ("Isolation Forest", float(details.get("isolation_forest", 0)), float(weight_map.get("if", 0.1))),
            ("LOF", float(details.get("lof", 0)), float(weight_map.get("lof", 0.2))),
            ("Autoencoder", float(details.get("autoencoder", 0)), float(weight_map.get("ae", 0.7))),
            ("Score final", score, 1.0),
        ]

        row_markup = []
        for name, value, weight in component_scores:
            color = DANGER if value >= threshold else (WARNING if value >= max(0.4, threshold - 0.08) else SUCCESS)
            row_markup.append(
                f'<div class="score-row">'
                f'<div class="score-name">{name}</div>'
                f'<div class="score-weight">x{weight:.1f}</div>'
                f'<div class="score-track">'
                f'<div class="score-fill" style="width:{value * 100:.0f}%; background:{color}"></div>'
                f'</div>'
                f'<div class="score-value" style="color:{color}">{value:.4f}</div>'
                f'</div>'
            )

        _scores_html = "".join(row_markup)
        st.markdown(
            "<div class=\"panel\" style=\"margin-top:1rem\">"
            "<div class=\"panel-title\">Detail des scores</div>"
            "<div class=\"panel-heading\">Contributions de chaque composant</div>"
            + _scores_html +
            "</div>",
            unsafe_allow_html=True,
        )

        safe_warning_band = max(0.0, threshold - 0.08)
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=score,
                number=dict(valueformat=".4f", font=dict(size=34, color="#eef4ff")),
                gauge=dict(
                    axis=dict(
                        range=[0, 1],
                        tickcolor="#93a7c0",
                        tickfont=dict(size=10, color="#93a7c0"),
                    ),
                    bar=dict(color=DANGER if is_anomaly else SUCCESS, thickness=0.28),
                    bgcolor="rgba(9,22,37,0.82)",
                    bordercolor="rgba(148,163,184,0.16)",
                    steps=[
                        dict(range=[0, safe_warning_band], color="rgba(34,197,94,0.18)"),
                        dict(range=[safe_warning_band, threshold], color="rgba(245,158,11,0.18)"),
                        dict(range=[threshold, 1], color="rgba(251,113,133,0.18)"),
                    ],
                    threshold=dict(
                        line=dict(color="#eef4ff", width=2),
                        thickness=0.85,
                        value=threshold,
                    ),
                ),
            )
        )
        gauge.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#eef4ff"),
            height=280,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        st.plotly_chart(gauge, use_container_width=True)

        st.markdown(
            f"""
            <div class="callout info">
                Le modele utilise <strong>{model_used}</strong> avec un seuil dynamique a
                <strong>{threshold:.3f}</strong>
                {" (percentile " + str(threshold_percentile) + ")" if threshold_percentile is not None else ""}.
                Les pourcentages Anomalie / Normal correspondent au rang du score final
                face au dataset de reference.
            </div>
            """,
            unsafe_allow_html=True,
        )
