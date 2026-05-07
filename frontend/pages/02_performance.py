"""
Performance page — metriques du meilleur modele deploye.

Routes backend utilisees :
  GET /api/metrics/evaluate       → metriques completes
  GET /api/metrics/viz?type=roc       → courbe ROC
  GET /api/metrics/viz?type=confusion → matrice de confusion
  GET /api/metrics/viz?type=scores    → distribution des scores
  GET /api/metrics/viz?type=pca       → projection PCA
"""

import os
import sys

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (  # noqa: E402
    ACCENT,
    DANGER,
    PLOTLY_LAYOUT,
    SUCCESS,
    WARNING,
    PAGE_CONFIG,
    api_get,
    explain_api_error,
    format_number,
    render_app_shell,
    render_metric_cards,
    render_page_header,
)

st.set_page_config(**PAGE_CONFIG)
render_app_shell("performance")

# ── Chargement des metriques ──────────────────────────────────────────────────

try:
    eval_data = api_get("/api/metrics/evaluate", timeout=60)
except Exception as exc:
    st.markdown(
        f"""
        <div class="callout danger">
            Impossible de charger les metriques du modele.<br>
            Detail : {explain_api_error(exc)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

metrics    = eval_data.get("metrics", {})
model_name = eval_data.get("model", "Modele deploye")

if not metrics:
    st.markdown(
        '<div class="callout warn">Aucune metrique retournee par le backend.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── En-tete ────────────────────────────────────────────────────────────────────

render_page_header(
    "Performance du modele",
    "Evaluer le meilleur modele sur le test set et comprendre ses resultats visuellement.",
    (
        "Toutes les metriques sont calculees sur le jeu de test UNSW-NB15 complet "
        "(82 332 connexions). Les graphiques sont generes par le backend."
    ),
    [
        model_name,
        f"F1 {format_number(metrics.get('f1'))}",
        f"AUC {format_number(metrics.get('roc_auc'))}",
    ],
)

render_metric_cards(
    [
        {
            "label": "F1-score",
            "value": format_number(metrics.get("f1")),
            "sub":   "harmonic mean precision / recall",
            "tone":  "success",
        },
        {
            "label": "ROC-AUC",
            "value": format_number(metrics.get("roc_auc")),
            "sub":   "separation globale",
            "tone":  "accent",
        },
        {
            "label": "Recall",
            "value": format_number(metrics.get("recall")),
            "sub":   "couverture des attaques",
        },
        {
            "label": "Precision",
            "value": format_number(metrics.get("precision")),
            "sub":   "qualite des alertes levees",
        },
    ]
)

# Anomalies detectees vs reelles
n_det  = metrics.get("n_anomalies_detected", 0)
n_true = metrics.get("n_true_anomalies", 0)
inf_s  = metrics.get("inference_s", 0)

st.markdown(
    f"""
    <div class="callout info">
        <strong>{n_det:,}</strong> anomalies detectees sur <strong>{n_true:,}</strong> reelles
        &nbsp;·&nbsp; Inference : <strong>{inf_s:.2f}s</strong> sur le test set complet.
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Onglets ────────────────────────────────────────────────────────────────────

tab_roc, tab_confusion, tab_scores, tab_pca = st.tabs(
    ["Courbe ROC", "Confusion", "Distribution des scores", "Projection PCA"]
)

# ── Courbe ROC ─────────────────────────────────────────────────────────────────

with tab_roc:
    with st.spinner("Chargement de la courbe ROC..."):
        try:
            roc_payload = api_get("/api/metrics/viz", params={"type": "roc"}, timeout=120)
        except Exception as exc:
            st.markdown(
                f'<div class="callout danger">Impossible de recuperer la courbe ROC.<br>{explain_api_error(exc)}</div>',
                unsafe_allow_html=True,
            )
        else:
            roc_data = roc_payload.get("data", {})
            if not roc_data or "fpr" not in roc_data:
                st.info("Donnees ROC non disponibles.")
            else:
                auc_val = metrics.get("roc_auc", 0)
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=[0, 1], y=[0, 1],
                    mode="lines", name="Aleatoire",
                    line=dict(color="#94a3b8", dash="dash", width=1.5),
                ))
                fig.add_trace(go.Scatter(
                    x=roc_data["fpr"], y=roc_data["tpr"],
                    mode="lines",
                    name=f"{model_name} (AUC={auc_val:.4f})",
                    line=dict(color="#059669", width=3),
                ))
                fig.update_layout(
                    **PLOTLY_LAYOUT,
                    height=500,
                    xaxis_title="Taux de faux positifs",
                    yaxis_title="Taux de vrais positifs",
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown(
                    """
                    <div class="callout info">
                        La courbe ROC mesure la capacite du modele a separer normal et anomalie
                        a tous les seuils possibles. Un AUC proche de 1 indique une separation quasi-parfaite.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# ── Matrice de confusion ───────────────────────────────────────────────────────

with tab_confusion:
    with st.spinner("Chargement de la matrice de confusion..."):
        try:
            cm_payload = api_get("/api/metrics/viz", params={"type": "confusion"}, timeout=120)
        except Exception as exc:
            st.markdown(
                f'<div class="callout danger">Impossible de recuperer la matrice de confusion.<br>{explain_api_error(exc)}</div>',
                unsafe_allow_html=True,
            )
        else:
            cm_data = cm_payload.get("data", {})
            if not cm_data or "z" not in cm_data:
                st.info("Donnees de confusion non disponibles.")
            else:
                matrix = cm_data["z"]
                total  = sum(sum(row) for row in matrix) or 1
                text_values = [
                    [
                        f"{matrix[r][c]:,}<br>{matrix[r][c] / total * 100:.1f}%"
                        for c in range(2)
                    ]
                    for r in range(2)
                ]
                cm_col, info_col = st.columns([1.1, 0.9], gap="large")
                with cm_col:
                    heatmap = go.Figure(go.Heatmap(
                        z=matrix,
                        x=cm_data.get("x", ["Pred Normal", "Pred Anomalie"]),
                        y=cm_data.get("y", ["Reel Normal", "Reel Anomalie"]),
                        colorscale=[[0, "#e0f2fe"], [1, "#059669"]],
                        text=text_values,
                        texttemplate="%{text}",
                        showscale=False,
                    ))
                    _layout = {k: v for k, v in PLOTLY_LAYOUT.items() if k != "margin"}
                    heatmap.update_layout(
                        **_layout,
                        height=360,
                        margin=dict(l=80, r=20, t=60, b=35),
                        title=dict(
                            text=(
                                f"{model_name}<br>"
                                f"<span style='font-size:11px;color:#93a7c0'>"
                                f"F1 {metrics.get('f1', 0):.4f} | AUC {metrics.get('roc_auc', 0):.4f}"
                                "</span>"
                            ),
                            font=dict(color="#eef4ff", size=14),
                        ),
                    )
                    st.plotly_chart(heatmap, use_container_width=True)

                with info_col:
                    cm_raw = metrics.get("confusion_matrix", {})
                    tn = cm_raw.get("tn", 0)
                    fp = cm_raw.get("fp", 0)
                    fn = cm_raw.get("fn", 0)
                    tp = cm_raw.get("tp", 0)
                    st.markdown(
                        f"""
                        <div class="panel">
                            <div class="panel-title">Lecture de la matrice</div>
                            <div class="panel-heading">Vrais et faux positifs</div>
                            <div class="stat-list" style="margin-top:0.8rem">
                                <div class="stat-line">
                                    <span class="stat-key">Vrais negatifs (TN)</span>
                                    <span class="stat-value">{tn:,}</span>
                                </div>
                                <div class="stat-line">
                                    <span class="stat-key">Faux positifs (FP)</span>
                                    <span class="stat-value" style="color:var(--warning)">{fp:,}</span>
                                </div>
                                <div class="stat-line">
                                    <span class="stat-key">Faux negatifs (FN)</span>
                                    <span class="stat-value" style="color:var(--danger)">{fn:,}</span>
                                </div>
                                <div class="stat-line">
                                    <span class="stat-key">Vrais positifs (TP)</span>
                                    <span class="stat-value" style="color:var(--success)">{tp:,}</span>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

# ── Distribution des scores ────────────────────────────────────────────────────

with tab_scores:
    with st.spinner("Chargement des distributions de scores..."):
        try:
            score_payload = api_get("/api/metrics/viz", params={"type": "scores"}, timeout=120)
        except Exception as exc:
            st.markdown(
                f'<div class="callout danger">Impossible de recuperer les distributions.<br>{explain_api_error(exc)}</div>',
                unsafe_allow_html=True,
            )
        else:
            score_data = score_payload.get("data", {})
            if not score_data:
                st.info("Distributions de scores non disponibles.")
            else:
                d = list(score_data.values())[0]  # un seul modele
                percentiles = d.get("percentiles", {})

                fig = go.Figure()
                fig.add_trace(go.Histogram(
                    x=d.get("normal", []),
                    name="Normal",
                    marker_color="#2563eb",
                    opacity=0.70,
                    nbinsx=50,
                    histnorm="probability density",
                ))
                fig.add_trace(go.Histogram(
                    x=d.get("anomaly", []),
                    name="Anomalie",
                    marker_color="#dc2626",
                    opacity=0.62,
                    nbinsx=50,
                    histnorm="probability density",
                ))
                fig.update_layout(
                    **PLOTLY_LAYOUT,
                    barmode="overlay",
                    height=440,
                    xaxis_title="Score d'anomalie [0-1]",
                    yaxis_title="Densite de probabilite",
                )
                st.plotly_chart(fig, use_container_width=True)

                p_col1, p_col2, p_col3 = st.columns(3)
                p_col1.metric("Mediane (p50)", percentiles.get("p50", "-"))
                p_col2.metric("p90",           percentiles.get("p90", "-"))
                p_col3.metric("p95",           percentiles.get("p95", "-"))

                st.markdown(
                    """
                    <div class="callout info">
                        Un bon modele produit deux distributions bien separees : les scores normaux
                        restent bas, les scores anormaux s'accumulent vers 1. Plus le chevauchement
                        est faible, plus le seuil peut etre ajuste finement.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# ── Projection PCA ────────────────────────────────────────────────────────────

with tab_pca:
    with st.spinner("Chargement de la projection PCA..."):
        try:
            pca_payload = api_get("/api/metrics/viz", params={"type": "pca"}, timeout=120)
        except Exception as exc:
            st.markdown(
                f'<div class="callout danger">Impossible de recuperer la projection PCA.<br>{explain_api_error(exc)}</div>',
                unsafe_allow_html=True,
            )
        else:
            pca_data = pca_payload.get("data", {})
            if not pca_data or "x" not in pca_data:
                st.info("Donnees PCA non disponibles.")
            else:
                labels   = pca_data.get("labels", [])
                scores   = pca_data.get("scores", [])
                explained = pca_data.get("explained_variance", [0, 0])

                fig = go.Figure()
                for label_val, color, label_name in ((0, "#2563eb", "Normal"), (1, "#dc2626", "Anomalie")):
                    idx = [i for i, l in enumerate(labels) if l == label_val]
                    fig.add_trace(go.Scatter(
                        x=[pca_data["x"][i] for i in idx],
                        y=[pca_data["y"][i] for i in idx],
                        mode="markers",
                        name=label_name,
                        marker=dict(color=color, size=4, opacity=0.60),
                        text=[f"Score {scores[i]:.3f}" for i in idx] if scores else None,
                        hovertemplate="%{text}<extra></extra>" if scores else None,
                    ))
                fig.update_layout(
                    **PLOTLY_LAYOUT,
                    height=540,
                    xaxis_title=pca_data.get("pc1_label", "PC1"),
                    yaxis_title=pca_data.get("pc2_label", "PC2"),
                    title=dict(
                        text=(
                            f"{model_name}<br>"
                            f"<span style='font-size:11px;color:#93a7c0'>"
                            f"Variance expliquee {explained[0]:.1%} + {explained[1]:.1%}"
                            "</span>"
                        ),
                        font=dict(color="#eef4ff", size=15),
                    ),
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown(
                    """
                    <div class="callout info">
                        La projection PCA reste une vue de lecture, pas une preuve de separabilite parfaite.
                        Elle aide a reperer les zones de melange ou les frontieres deviennent ambigues.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )