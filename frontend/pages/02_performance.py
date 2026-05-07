"""
<<<<<<< HEAD
Performance page — metriques du meilleur modele deploye.

Routes backend utilisees :
  GET /api/metrics/evaluate       → metriques completes
  GET /api/metrics/viz?type=roc       → courbe ROC
  GET /api/metrics/viz?type=confusion → matrice de confusion
  GET /api/metrics/viz?type=scores    → distribution des scores
  GET /api/metrics/viz?type=pca       → projection PCA
=======
Model performance comparison page.
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
"""

import os
import sys

<<<<<<< HEAD
=======
import pandas as pd
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (  # noqa: E402
    ACCENT,
    DANGER,
<<<<<<< HEAD
    PLOTLY_LAYOUT,
    SUCCESS,
    WARNING,
    PAGE_CONFIG,
=======
    PAGE_CONFIG,
    PALETTE,
    PLOTLY_LAYOUT,
    SUCCESS,
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
    api_get,
    explain_api_error,
    format_number,
    render_app_shell,
    render_metric_cards,
    render_page_header,
)

st.set_page_config(**PAGE_CONFIG)
render_app_shell("performance")

<<<<<<< HEAD
# ── Chargement des metriques ──────────────────────────────────────────────────

try:
    eval_data = api_get("/api/metrics/evaluate", timeout=60)
=======
try:
    compare_data = api_get("/api/models/compare", timeout=30)
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
except Exception as exc:
    st.markdown(
        f"""
        <div class="callout danger">
<<<<<<< HEAD
            Impossible de charger les metriques du modele.<br>
=======
            Impossible de charger les metriques des modeles.<br>
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
            Detail : {explain_api_error(exc)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

<<<<<<< HEAD
metrics    = eval_data.get("metrics", {})
model_name = eval_data.get("model", "Modele deploye")

if not metrics:
    st.markdown(
        '<div class="callout warn">Aucune metrique retournee par le backend.</div>',
=======
metrics_raw = compare_data.get("metrics", [])
best_model = compare_data.get("best_model", "")
source = compare_data.get("source", "source non disponible")

if not metrics_raw:
    st.markdown(
        """
        <div class="callout warn">
            Aucune metrique n'a ete retournee par le backend.
        </div>
        """,
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
        unsafe_allow_html=True,
    )
    st.stop()

<<<<<<< HEAD
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
=======
df_metrics = pd.DataFrame(metrics_raw)
if "model" not in df_metrics.columns and df_metrics.index.name:
    df_metrics = df_metrics.reset_index().rename(columns={"index": "model"})

if "perf_score" in df_metrics.columns:
    df_metrics = df_metrics.sort_values("perf_score", ascending=False).reset_index(drop=True)

best_row = df_metrics[df_metrics["model"] == best_model].iloc[0] if best_model in df_metrics["model"].values else df_metrics.iloc[0]
model_names = df_metrics["model"].tolist() if "model" in df_metrics.columns else []

render_page_header(
    "Comparaison des modeles",
    "Evaluer les modeles sur les memes indicateurs et garder le modele deploye parfaitement lisible.",
    (
        "La page Performance utilise la meme base visuelle que la page Prediction: "
        "meme nom de modele, meme score composite et memes donnees backend."
    ),
    [
        f"Source: {source}",
        f"Meilleur modele: {best_model}",
        f"{len(df_metrics)} modeles",
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
    ],
)

render_metric_cards(
    [
        {
<<<<<<< HEAD
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
=======
            "label": "Meilleur F1-score",
            "value": format_number(best_row.get("f1")),
            "sub": best_row.get("model", ""),
            "tone": "success",
        },
        {
            "label": "ROC-AUC",
            "value": format_number(best_row.get("roc_auc")),
            "sub": "separation globale",
            "tone": "accent",
        },
        {
            "label": "Recall",
            "value": format_number(best_row.get("recall")),
            "sub": "couverture des attaques",
        },
        {
            "label": "Score composite",
            "value": format_number(best_row.get("perf_score")),
            "sub": "0.35 AUC + 0.30 F1 + 0.20 Recall + 0.15 Precision",
            "tone": "accent",
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
        },
    ]
)

<<<<<<< HEAD
# Anomalies detectees vs reelles
n_det  = metrics.get("n_anomalies_detected", 0)
n_true = metrics.get("n_true_anomalies", 0)
inf_s  = metrics.get("inference_s", 0)

st.markdown(
    f"""
    <div class="callout info">
        <strong>{n_det:,}</strong> anomalies detectees sur <strong>{n_true:,}</strong> reelles
        &nbsp;·&nbsp; Inference : <strong>{inf_s:.2f}s</strong> sur le test set complet.
=======
st.markdown(
    """
    <div class="callout info">
        Le score composite reste l'indicateur de selection principal. Il stabilise la lecture
        quand plusieurs modeles sont proches sur un seul score mais se differencient sur le
        rappel, la precision ou le comportement global.
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
    </div>
    """,
    unsafe_allow_html=True,
)

<<<<<<< HEAD
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
=======
tab_ranking, tab_roc, tab_confusion, tab_pca = st.tabs(
    ["Classement", "Courbes ROC", "Confusion", "Projection PCA"]
)

with tab_ranking:
    st.markdown('<div class="section-heading">Classement des modeles</div>', unsafe_allow_html=True)
    for rank, row in enumerate(df_metrics.itertuples(index=False), start=1):
        score = getattr(row, "perf_score", 0) or 0
        is_best = getattr(row, "model", "") == best_model
        badge = "<span class='tag-pill'>deployed</span>" if is_best else ""
        st.markdown(
            f"""
            <div class="ranking-row {'active' if is_best else ''}">
                <div class="ranking-rank">{rank:02d}</div>
                <div>
                    <div class="ranking-name">{getattr(row, 'model', '')} {badge}</div>
                    <div class="ranking-meta">
                        F1 {getattr(row, 'f1', 0):.4f} |
                        ROC-AUC {getattr(row, 'roc_auc', 0):.4f} |
                        Precision {getattr(row, 'precision', 0):.4f} |
                        Recall {getattr(row, 'recall', 0):.4f}
                    </div>
                    <div class="ranking-track">
                        <div class="ranking-fill" style="width:{score * 100:.0f}%"></div>
                    </div>
                </div>
                <div class="ranking-score">{score:.4f}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    chart_left, chart_right = st.columns([1.1, 0.9], gap="large")
    metric_columns = [column for column in ["f1", "roc_auc", "precision", "recall"] if column in df_metrics.columns]

    with chart_left:
        comparison_figure = go.Figure()
        for index, metric_name in enumerate(metric_columns):
            comparison_figure.add_trace(
                go.Bar(
                    name=metric_name.upper().replace("_", "-"),
                    x=df_metrics["model"],
                    y=df_metrics[metric_name],
                    marker=dict(color=PALETTE[index % len(PALETTE)]),
                    text=[f"{value:.3f}" for value in df_metrics[metric_name]],
                    textposition="outside",
                )
            )

        _override_keys = {"xaxis", "legend"}
        _xaxis = {**PLOTLY_LAYOUT.get("xaxis", {}), "tickangle": -18}
        _legend = {**PLOTLY_LAYOUT.get("legend", {}), "orientation": "h", "y": 1.08}
        _layout = {k: v for k, v in PLOTLY_LAYOUT.items() if k not in _override_keys}
        comparison_figure.update_layout(
            **_layout,
            barmode="group",
            height=430,
            xaxis=_xaxis,
            legend=_legend,
        )
        st.plotly_chart(comparison_figure, use_container_width=True)

    with chart_right:
        if "perf_score" in df_metrics.columns:
            score_figure = go.Figure(
                go.Bar(
                    x=df_metrics["perf_score"][::-1],
                    y=df_metrics["model"][::-1],
                    orientation="h",
                    marker=dict(
                        color=[
                            SUCCESS if model_name == best_model else ACCENT
                            for model_name in df_metrics["model"][::-1]
                        ]
                    ),
                    text=[f"{value:.4f}" for value in df_metrics["perf_score"][::-1]],
                    textposition="outside",
                )
            )
            score_figure.update_layout(
                **PLOTLY_LAYOUT,
                height=430,
                showlegend=False,
                xaxis_title="Score composite",
            )
            st.plotly_chart(score_figure, use_container_width=True)

with tab_roc:
    with st.spinner("Chargement des courbes ROC (premiere execution : 1-2 min)..."):
        try:
            roc_payload = api_get("/api/models/viz", params={"type": "roc"}, timeout=180)
        except Exception as exc:
            st.markdown(
                f"""
                <div class="callout danger">
                    Impossible de recuperer les courbes ROC.<br>
                    Detail : {explain_api_error(exc)}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            roc_curves = roc_payload.get("data", {})
            if not roc_curves:
                st.info("Aucune courbe ROC n'est disponible.")
            else:
                roc_figure = go.Figure()
                roc_figure.add_trace(
                    go.Scatter(
                        x=[0, 1],
                        y=[0, 1],
                        mode="lines",
                        name="Aleatoire",
                        line=dict(color="#94a3b8", dash="dash", width=1.5),
                    )
                )

                for index, (model_name, curve) in enumerate(roc_curves.items()):
                    auc_values = df_metrics.loc[df_metrics["model"] == model_name, "roc_auc"].values
                    auc_value = auc_values[0] if len(auc_values) else 0
                    is_best = model_name == best_model
                    roc_figure.add_trace(
                        go.Scatter(
                            x=curve["fpr"],
                            y=curve["tpr"],
                            mode="lines",
                            name=f"{model_name} (AUC={auc_value:.4f})",
                            line=dict(
                                color=PALETTE[index % len(PALETTE)],
                                width=3.2 if is_best else 1.8,
                            ),
                            opacity=1 if is_best else 0.78,
                        )
                    )

                roc_figure.update_layout(
                    **PLOTLY_LAYOUT,
                    height=520,
                    xaxis_title="Taux de faux positifs",
                    yaxis_title="Taux de vrais positifs",
                )
                st.plotly_chart(roc_figure, use_container_width=True)

with tab_confusion:
    with st.spinner("Chargement des matrices de confusion..."):
        try:
            confusion_payload = api_get("/api/models/viz", params={"type": "confusion"}, timeout=180)
        except Exception as exc:
            st.markdown(
                f"""
                <div class="callout danger">
                    Impossible de recuperer les matrices de confusion.<br>
                    Detail : {explain_api_error(exc)}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            confusion_list = confusion_payload.get("data", [])
            if not confusion_list:
                st.info("Aucune matrice de confusion n'est disponible.")
            else:
                for offset in range(0, len(confusion_list), 2):
                    cols = st.columns(min(2, len(confusion_list) - offset), gap="large")
                    for column, matrix_payload in zip(cols, confusion_list[offset:offset + 2]):
                        with column:
                            model_name = matrix_payload.get("model_name", "")
                            matrix = matrix_payload.get("z", [[0, 0], [0, 0]])
                            total = sum(sum(row) for row in matrix) or 1
                            text_values = [
                                [f"{matrix[row_idx][col_idx]:,}<br>{matrix[row_idx][col_idx] / total * 100:.1f}%" for col_idx in range(2)]
                                for row_idx in range(2)
                            ]

                            heatmap = go.Figure(
                                go.Heatmap(
                                    z=matrix,
                                    x=matrix_payload.get("x", ["Pred 0", "Pred 1"]),
                                    y=matrix_payload.get("y", ["True 0", "True 1"]),
                                    colorscale=[[0, "#112033"], [1, SUCCESS if model_name == best_model else ACCENT]],
                                    text=text_values,
                                    texttemplate="%{text}",
                                    showscale=False,
                                )
                            )
                            _layout_heatmap = {k: v for k, v in PLOTLY_LAYOUT.items() if k != "margin"}
                            heatmap.update_layout(
                                **_layout_heatmap,
                                height=310,
                                margin=dict(l=80, r=20, t=60, b=35),
                                title=dict(
                                    text=(
                                        f"{model_name}<br>"
                                        f"<span style='font-size:11px;color:#93a7c0'>"
                                        f"F1 {matrix_payload.get('f1', 0):.4f} | "
                                        f"AUC {matrix_payload.get('roc_auc', 0):.4f}"
                                        "</span>"
                                    ),
                                    font=dict(color="#eef4ff", size=14),
                                ),
                            )
                            st.plotly_chart(heatmap, use_container_width=True)

with tab_pca:
    selected_model = st.selectbox("Modele a projeter", options=model_names)
    with st.spinner("Chargement de la projection PCA..."):
        try:
            pca_payload = api_get(
                "/api/models/viz",
                params={"type": "pca", "model": selected_model},
                timeout=180,
            )
        except Exception as exc:
            st.markdown(
                f"""
                <div class="callout danger">
                    Impossible de recuperer la projection PCA.<br>
                    Detail : {explain_api_error(exc)}
                </div>
                """,
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
                unsafe_allow_html=True,
            )
        else:
            pca_data = pca_payload.get("data", {})
            if not pca_data or "x" not in pca_data:
<<<<<<< HEAD
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
=======
                st.info("Les donnees PCA ne sont pas disponibles.")
            else:
                labels = pca_data.get("labels", [])
                scores = pca_data.get("scores", [])
                explained = pca_data.get("explained_variance", [0, 0])

                pca_figure = go.Figure()
                for label_value, color, label_name in ((0, ACCENT, "Normal"), (1, DANGER, "Anomalie")):
                    indices = [index for index, label in enumerate(labels) if label == label_value]
                    pca_figure.add_trace(
                        go.Scatter(
                            x=[pca_data["x"][index] for index in indices],
                            y=[pca_data["y"][index] for index in indices],
                            mode="markers",
                            name=label_name,
                            marker=dict(color=color, size=4, opacity=0.62),
                            text=[f"Score {scores[index]:.3f}" for index in indices] if scores else None,
                            hovertemplate="%{text}<extra></extra>" if scores else None,
                        )
                    )

                pca_figure.update_layout(
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
                    **PLOTLY_LAYOUT,
                    height=540,
                    xaxis_title=pca_data.get("pc1_label", "PC1"),
                    yaxis_title=pca_data.get("pc2_label", "PC2"),
                    title=dict(
                        text=(
<<<<<<< HEAD
                            f"{model_name}<br>"
                            f"<span style='font-size:11px;color:#93a7c0'>"
                            f"Variance expliquee {explained[0]:.1%} + {explained[1]:.1%}"
=======
                            f"{selected_model}<br>"
                            f"<span style='font-size:11px;color:#93a7c0'>"
                            f"Variance expliquee {explained[0]:.1%} + {explained[1]:.1%} = {sum(explained):.1%}"
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
                            "</span>"
                        ),
                        font=dict(color="#eef4ff", size=15),
                    ),
                )
<<<<<<< HEAD
                st.plotly_chart(fig, use_container_width=True)
=======
                st.plotly_chart(pca_figure, use_container_width=True)

>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
                st.markdown(
                    """
                    <div class="callout info">
                        La projection PCA reste une vue de lecture, pas une preuve de separabilite parfaite.
<<<<<<< HEAD
                        Elle aide a reperer les zones de melange ou les frontieres deviennent ambigues.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
=======
                        Elle aide surtout a reperer les zones de melange ou les frontieres deviennent plus
                        ambigues pour les modeles.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
