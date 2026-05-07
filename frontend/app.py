"""
Landing page — NetGuard.

Routes backend utilisees :
  GET /api/dataset/info      → stats du dataset
  GET /api/metrics/evaluate  → metriques du meilleur modele
  GET /api/predict/info      → infos sur le modele deploye
"""

import html
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from config import (
    PAGE_CONFIG,
    api_get,
    explain_api_error,
    format_number,
    format_percent,
    render_app_shell,
    render_metric_cards,
    render_page_header,
)

st.set_page_config(**PAGE_CONFIG)
render_app_shell("home")

# ── Chargement des donnees ─────────────────────────────────────────────────────

dataset_info   = None
metrics_info   = None
model_info     = None
load_errors    = []

for label, path, timeout in (
    ("dataset",    "/api/dataset/info",     10),
    ("metrics",    "/api/metrics/evaluate", 30),
    ("prediction", "/api/predict/info",     10),
):
    try:
        payload = api_get(path, timeout=timeout)
        if label == "dataset":
            dataset_info = payload
        elif label == "metrics":
            metrics_info = payload
        else:
            model_info = payload
    except Exception as exc:
        load_errors.append(f"{label}: {explain_api_error(exc)}")

overview     = dataset_info.get("overview", {})    if dataset_info else {}
test_set     = overview.get("test_set", {})
train_set    = overview.get("train_set", {})
best_model   = model_info.get("best_model", {})    if model_info  else {}
best_metrics = best_model.get("metrics", {})
eval_metrics = metrics_info.get("metrics", {})     if metrics_info else {}

# ── En-tete ────────────────────────────────────────────────────────────────────

header_badges = []
if test_set:
    header_badges.append(f"{test_set.get('n_rows', 0):,} connexions test")
if best_model:
    header_badges.append(best_model.get("name", "Modele deploye"))
if eval_metrics:
    header_badges.append(f"AUC {format_number(eval_metrics.get('roc_auc'))}")

render_page_header(
    "NetGuard Control Center",
    "Explorer le dataset, evaluer le modele et tester des predictions.",
    (
        "Le frontend repose sur une seule experience Streamlit coherente. "
        "Chaque page partage le meme shell et les memes composants visuels."
    ),
    header_badges,
)

# ── Erreurs de chargement ─────────────────────────────────────────────────────

if load_errors:
    error_lines = "".join(f"<li>{error}</li>" for error in load_errors)
    st.markdown(
        f"""
        <div class="callout warn">
            Certaines donnees n'ont pas pu etre chargees. L'interface reste navigable,
            mais les pages detaillees dependront du backend.
            <ul style="margin:0.75rem 0 0 1rem;color:#f8d6a0;">
                {error_lines}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Metriques cles ─────────────────────────────────────────────────────────────

render_metric_cards(
    [
        {
            "label": "Train set",
            "value": f"{train_set.get('n_rows', 0):,}" if train_set else "-",
            "sub":   "observations pour l'apprentissage",
            "tone":  "accent",
        },
        {
            "label": "Test set",
            "value": f"{test_set.get('n_rows', 0):,}" if test_set else "-",
            "sub":   "observations pour l'evaluation",
        },
        {
            "label": "F1-Score",
            "value": format_number(eval_metrics.get("f1")) if eval_metrics else "-",
            "sub":   "meilleur modele deploye",
            "tone":  "success",
        },
        {
            "label": "ROC-AUC",
            "value": format_number(eval_metrics.get("roc_auc")) if eval_metrics else "-",
            "sub":   "qualite de separation globale",
            "tone":  "accent",
        },
    ]
)

# ── Vue d'ensemble + modele deploye ──────────────────────────────────────────

left_col, right_col = st.columns([1.1, 0.9], gap="large")

with left_col:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">Vue d'ensemble</div>
            <div class="panel-heading">Ce que l'application couvre</div>
            <p class="panel-copy">
                L'accueil sert de tableau de bord. Les vues detaillees sont separees
                dans les pages Streamlit dediees pour eviter les doublons de logique
                et garder une navigation claire.
            </p>
            <div class="stat-list" style="margin-top:1rem">
                <div class="stat-line">
                    <span class="stat-key">Dataset</span>
                    <span class="stat-value">UNSW-NB15, statistiques et echantillons</span>
                </div>
                <div class="stat-line">
                    <span class="stat-key">Performance</span>
                    <span class="stat-value">ROC, confusion, scores, PCA</span>
                </div>
                <div class="stat-line">
                    <span class="stat-key">Prediction</span>
                    <span class="stat-value">Formulaire, presets, score et seuil</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right_col:
    if best_model:
        components = best_model.get("components", [])
        component_rows = "".join(
            (
                '<div class="stat-line">'
                f'<span class="stat-key">{html.escape(str(c.get("name", "")))}</span>'
                f'<span class="stat-value">{c.get("weight", 0):.1f}</span>'
                "</div>"
            )
            for c in components
        )
        # metriques depuis /api/predict/info ou /api/metrics/evaluate
        f1_val  = format_number(best_metrics.get("f1_score") or eval_metrics.get("f1"))
        auc_val = format_number(best_metrics.get("roc_auc") or eval_metrics.get("roc_auc"))
        p_val   = format_number(best_metrics.get("precision") or eval_metrics.get("precision"))
        r_val   = format_number(best_metrics.get("recall") or eval_metrics.get("recall"))

        st.markdown(
            '<div class="panel">'
            '<div class="panel-title">Modele deploye</div>'
            f'<div class="panel-heading">{html.escape(str(best_model.get("name", "Indisponible")))}</div>'
            f'<p class="panel-copy">{html.escape(str(best_model.get("decision_formula", "")))}</p>'
            '<div class="stat-list" style="margin-top:1rem">'
            f'<div class="stat-line"><span class="stat-key">F1-score</span><span class="stat-value">{f1_val}</span></div>'
            f'<div class="stat-line"><span class="stat-key">ROC-AUC</span><span class="stat-value">{auc_val}</span></div>'
            f'<div class="stat-line"><span class="stat-key">Precision / Recall</span><span class="stat-value">{p_val} / {r_val}</span></div>'
            f'{component_rows}'
            "</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">Etat backend</div>
                <div class="panel-heading">Les metadonnees du modele ne sont pas disponibles.</div>
                <p class="panel-copy">
                    Si le backend n'est pas lance, les pages restent accessibles
                    mais les visualisations afficheront une erreur descriptive.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Parcours rapide ────────────────────────────────────────────────────────────

st.markdown('<div class="section-kicker">Parcours</div>', unsafe_allow_html=True)
st.markdown('<div class="section-heading">Trois entrees claires pour avancer vite</div>', unsafe_allow_html=True)

card_cols = st.columns(3, gap="large")

with card_cols[0]:
    st.markdown(
        f"""
        <div class="quick-card">
            <div class="quick-card-title">Dataset</div>
            <div class="quick-card-copy">
                Examiner la distribution des classes, les groupes de features,
                les statistiques descriptives et un extrait du test set.
            </div>
            <div class="tag-cloud">
                <span class="tag-pill">{test_set.get("n_features", 0) if test_set else "-"} features</span>
                <span class="tag-pill">{format_percent(test_set.get("anomaly_rate")) if test_set else "-"}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Ouvrir le dataset", key="open-dataset", use_container_width=True):
        st.switch_page("pages/01_dataset.py")

with card_cols[1]:
    st.markdown(
        f"""
        <div class="quick-card">
            <div class="quick-card-title">Performance</div>
            <div class="quick-card-copy">
                Evaluer le modele sur le test set, visualiser la courbe ROC,
                la matrice de confusion et la projection PCA.
            </div>
            <div class="tag-cloud">
                <span class="tag-pill">F1 {format_number(eval_metrics.get("f1")) if eval_metrics else "-"}</span>
                <span class="tag-pill">AUC {format_number(eval_metrics.get("roc_auc")) if eval_metrics else "-"}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Voir les performances", key="open-performance", use_container_width=True):
        st.switch_page("pages/02_performance.py")

with card_cols[2]:
    threshold_copy = best_model.get("threshold", "seuil indisponible") if best_model else "seuil indisponible"
    st.markdown(
        f"""
        <div class="quick-card">
            <div class="quick-card-title">Prediction</div>
            <div class="quick-card-copy">
                Tester des connexions reseau via un formulaire clair, des presets
                de scenarios et un rendu du score final avec seuil dynamique.
            </div>
            <div class="tag-cloud">
                <span class="tag-pill">{best_model.get("name", "Modele") if best_model else "Modele"}</span>
                <span class="tag-pill">{threshold_copy}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Analyser une connexion", key="open-prediction", type="primary", use_container_width=True):
        st.switch_page("pages/03_prediction.py")

# ── Signal metier ─────────────────────────────────────────────────────────────

if dataset_info or metrics_info:
    insight_left, insight_right = st.columns([0.95, 1.05], gap="large")

    with insight_left:
        label_dist = dataset_info.get("label_distribution", {}) if dataset_info else {}
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Signal metier</div>
                <div class="panel-heading">Ce que racontent les chiffres d'entree</div>
                <p class="panel-copy">
                    Le jeu de test contient <strong>{test_set.get('n_anomalies', 0):,}</strong>
                    anomalies sur <strong>{test_set.get('n_rows', 0):,}</strong> connexions.
                    Ce ratio est utile pour interpreter les predictions et le seuil applique.
                </p>
                <div class="stat-list" style="margin-top:1rem">
                    <div class="stat-line">
                        <span class="stat-key">Trafic normal</span>
                        <span class="stat-value">{label_dist.get('normal', 0):,}</span>
                    </div>
                    <div class="stat-line">
                        <span class="stat-key">Trafic anormal</span>
                        <span class="stat-value">{label_dist.get('anomaly', 0):,}</span>
                    </div>
                    <div class="stat-line">
                        <span class="stat-key">Taux d'anomalies</span>
                        <span class="stat-value">{format_percent(test_set.get('anomaly_rate'))}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with insight_right:
        cm = eval_metrics.get("confusion_matrix", {}) if eval_metrics else {}
        n_detected_raw = eval_metrics.get("n_anomalies_detected") if eval_metrics else None
        n_true_raw     = eval_metrics.get("n_true_anomalies")     if eval_metrics else None
        n_detected_str = f"{n_detected_raw:,}" if isinstance(n_detected_raw, int) else "-"
        n_true_str     = f"{n_true_raw:,}"     if isinstance(n_true_raw, int)     else "-"
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Selection du modele</div>
                <div class="panel-heading">{html.escape(str(best_model.get("name", "Modele deploye")))}</div>
                <p class="panel-copy">
                    La page Performance montre le detail des metriques, les distributions
                    de scores et la projection PCA pour garder une lecture claire de bout
                    en bout.
                </p>
                <div class="stat-list" style="margin-top:1rem">
                    <div class="stat-line">
                        <span class="stat-key">F1-score</span>
                        <span class="stat-value">{format_number(eval_metrics.get("f1")) if eval_metrics else "-"}</span>
                    </div>
                    <div class="stat-line">
                        <span class="stat-key">ROC-AUC</span>
                        <span class="stat-value">{format_number(eval_metrics.get("roc_auc")) if eval_metrics else "-"}</span>
                    </div>
                    <div class="stat-line">
                        <span class="stat-key">Anomalies detectees / reelles</span>
                        <span class="stat-value">{n_detected_str} / {n_true_str}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )