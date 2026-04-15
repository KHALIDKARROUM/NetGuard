"""
Landing page for the Streamlit frontend.
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

dataset_info = None
compare_info = None
best_model_info = None
load_errors = []

for label, path, timeout in (
    ("dataset", "/api/dataset/info", 10),
    ("performance", "/api/models/compare", 30),
    ("prediction", "/api/predict/best_model", 10),
):
    try:
        payload = api_get(path, timeout=timeout)
        if label == "dataset":
            dataset_info = payload
        elif label == "performance":
            compare_info = payload
        else:
            best_model_info = payload
    except Exception as exc:
        load_errors.append(f"{label}: {explain_api_error(exc)}")

overview = dataset_info.get("overview", {}) if dataset_info else {}
test_set = overview.get("test_set", {})
train_set = overview.get("train_set", {})
best_model = best_model_info.get("best_model", {}) if best_model_info else {}
best_metrics = best_model.get("metrics", {})
compare_metrics = compare_info.get("metrics", []) if compare_info else []

header_badges = []
if test_set:
    header_badges.append(f"{test_set.get('n_rows', 0):,} connexions test")
if compare_metrics:
    header_badges.append(f"{len(compare_metrics)} modeles compares")
if best_model:
    header_badges.append(best_model.get("name", "Modele deploye"))

render_page_header(
    "NetGuard Control Center",
    "Une interface unique pour explorer le dataset, comparer les modeles et tester des predictions.",
    (
        "Le frontend repose maintenant sur une seule experience Streamlit coherente. "
        "Chaque page partage le meme shell, les memes composants et une gestion "
        "d'erreurs plus claire quand le backend n'est pas disponible."
    ),
    header_badges,
)

if load_errors:
    error_lines = "".join(f"<li>{error}</li>" for error in load_errors)
    st.markdown(
        f"""
        <div class="callout warn">
            Certaines donnees n'ont pas pu etre chargees. L'interface reste navigable,
            mais les pages detaillees dependront du backend pour afficher leurs contenus.
            <ul style="margin:0.75rem 0 0 1rem; color:#f8d6a0;">
                {error_lines}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_metric_cards(
    [
        {
            "label": "Train set",
            "value": f"{train_set.get('n_rows', 0):,}" if train_set else "-",
            "sub": "observations pour l'apprentissage",
            "tone": "accent",
        },
        {
            "label": "Test set",
            "value": f"{test_set.get('n_rows', 0):,}" if test_set else "-",
            "sub": "observations pour l'evaluation",
        },
        {
            "label": "Features",
            "value": str(test_set.get("n_features", 0)) if test_set else "-",
            "sub": "variables exploitees par le modele",
        },
        {
            "label": "Meilleur ROC-AUC",
            "value": format_number(best_metrics.get("roc_auc")) if best_metrics else "-",
            "sub": "qualite du modele deploye",
            "tone": "success",
        },
    ]
)

left_col, right_col = st.columns([1.1, 0.9], gap="large")

with left_col:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">Vue d'ensemble</div>
            <div class="panel-heading">Ce que l'application couvre maintenant</div>
            <p class="panel-copy">
                L'accueil sert de tableau de bord. Les vues detaillees ont ete separees
                proprement dans les pages Streamlit dediees afin d'eviter les doublons
                de logique, les incoherences de style et les comportements de navigation
                confus entre l'accueil et <code>frontend/pages</code>.
            </p>
            <div class="stat-list" style="margin-top:1rem">
                <div class="stat-line">
                    <span class="stat-key">Dataset</span>
                    <span class="stat-value">UNSW-NB15, statistiques et echantillons</span>
                </div>
                <div class="stat-line">
                    <span class="stat-key">Modeles</span>
                    <span class="stat-value">Classement, ROC, confusion, PCA</span>
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
                f'<span class="stat-key">{html.escape(str(component.get("name", "")))}</span>'
                f'<span class="stat-value">{component.get("weight", 0):.1f}</span>'
                "</div>"
            )
            for component in components
        )

        panel_markup = (
            '<div class="panel">'
            '<div class="panel-title">Modele deploye</div>'
            f'<div class="panel-heading">{html.escape(str(best_model.get("name", "Indisponible")))}</div>'
            f'<p class="panel-copy">{html.escape(str(best_model.get("decision_formula", "Configuration non disponible")))}</p>'
            '<div class="stat-list" style="margin-top:1rem">'
            '<div class="stat-line">'
            '<span class="stat-key">F1-score</span>'
            f'<span class="stat-value">{format_number(best_metrics.get("f1_score"))}</span>'
            "</div>"
            '<div class="stat-line">'
            '<span class="stat-key">ROC-AUC</span>'
            f'<span class="stat-value">{format_number(best_metrics.get("roc_auc"))}</span>'
            "</div>"
            '<div class="stat-line">'
            '<span class="stat-key">Score composite</span>'
            f'<span class="stat-value">{format_number(best_metrics.get("perf_score"))}</span>'
            "</div>"
            f"{component_rows}"
            "</div>"
            "</div>"
        )
        st.markdown(panel_markup, unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">Etat backend</div>
                <div class="panel-heading">Les metadonnees du modele ne sont pas disponibles.</div>
                <p class="panel-copy">
                    Si le backend n'est pas lance, les pages restent accessibles mais les
                    visualisations et predictions afficheront une erreur descriptive.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown('<div class="section-kicker">Parcours</div>', unsafe_allow_html=True)
st.markdown('<div class="section-heading">Trois entrees claires pour avancer vite</div>', unsafe_allow_html=True)

card_cols = st.columns(3, gap="large")

with card_cols[0]:
    st.markdown(
        f"""
        <div class="quick-card">
            <div class="quick-card-title">Dataset</div>
            <div class="quick-card-copy">
                Examiner la distribution des classes, les groupes de features, les statistiques
                descriptives et un extrait du test set.
            </div>
            <div class="tag-cloud">
                <span class="tag-pill">{test_set.get("n_features", 0) if test_set else "-" } features</span>
                <span class="tag-pill">{format_percent(test_set.get("anomaly_rate")) if test_set else "-"}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Ouvrir le dataset", key="open-dataset", use_container_width=True):
        st.switch_page("pages/01_dataset.py")

with card_cols[1]:
    source_label = compare_info.get("source", "source non disponible") if compare_info else "source non disponible"
    st.markdown(
        f"""
        <div class="quick-card">
            <div class="quick-card-title">Performance</div>
            <div class="quick-card-copy">
                Comparer les modeles sur les memes indicateurs, visualiser les courbes ROC,
                les matrices de confusion et la projection PCA.
            </div>
            <div class="tag-cloud">
                <span class="tag-pill">{len(compare_metrics) if compare_metrics else "-" } modeles</span>
                <span class="tag-pill">{source_label}</span>
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
                Tester des connexions reseau via un formulaire plus lisible, des presets
                de scenarios et un rendu du score final sans valeur de seuil hardcodee.
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

if dataset_info or compare_info:
    insight_left, insight_right = st.columns([0.95, 1.05], gap="large")

    with insight_left:
        label_dist = dataset_info.get("label_distribution", {}) if dataset_info else {}
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Signal metier</div>
                <div class="panel-heading">Ce que racontent les chiffres d'entree</div>
                <p class="panel-copy">
                    Le jeu de test contient <strong>{test_set.get('n_anomalies', 0):,}</strong> anomalies
                    sur <strong>{test_set.get('n_rows', 0):,}</strong> connexions. Ce ratio est utile pour
                    interpreter les predictions et le seuil applique par le modele.
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
        best_compare_name = compare_info.get("best_model", "-") if compare_info else "-"
        st.markdown(
            f"""
            <div class="panel">
                <div class="panel-title">Selection du modele</div>
                <div class="panel-heading">{best_compare_name}</div>
                <p class="panel-copy">
                    La page Performance montre le classement complet et garde la meme lecture
                    visuelle que la page Prediction pour que les scores, le modele deploye et
                    le seuil restent alignes d'un bout a l'autre du frontend.
                </p>
                <div class="stat-list" style="margin-top:1rem">
                    <div class="stat-line">
                        <span class="stat-key">F1-score</span>
                        <span class="stat-value">{format_number(best_metrics.get('f1_score')) if best_metrics else '-'}</span>
                    </div>
                    <div class="stat-line">
                        <span class="stat-key">ROC-AUC</span>
                        <span class="stat-value">{format_number(best_metrics.get('roc_auc')) if best_metrics else '-'}</span>
                    </div>
                    <div class="stat-line">
                        <span class="stat-key">Precision / Recall</span>
                        <span class="stat-value">
                            {format_number(best_metrics.get('precision')) if best_metrics else '-'} /
                            {format_number(best_metrics.get('recall')) if best_metrics else '-'}
                        </span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
