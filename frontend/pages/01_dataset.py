"""
Dataset exploration page.
"""

import os
import sys

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (  # noqa: E402
    ACCENT,
    DANGER,
    PAGE_CONFIG,
    PLOTLY_LAYOUT,
    api_get,
    explain_api_error,
    format_percent,
    render_app_shell,
    render_metric_cards,
    render_page_header,
)

st.set_page_config(**PAGE_CONFIG)
render_app_shell("dataset")

try:
    info = api_get("/api/dataset/info", timeout=10)
except Exception as exc:
    st.markdown(
        f"""
        <div class="callout danger">
            Impossible de charger les informations du dataset depuis le backend.<br>
            Detail : {explain_api_error(exc)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

overview = info.get("overview", {})
test_set = overview.get("test_set", {})
train_set = overview.get("train_set", {})
label_dist = info.get("label_distribution", {})
feature_names = overview.get("feature_names", [])
numeric_stats = overview.get("numeric_stats", {})
source_file = info.get("source_file", "data/featured/test_featured.csv")

render_page_header(
    "Dataset UNSW-NB15",
    "Explorer les distributions, les groupes de features et la structure du jeu de test.",
    (
        "Cette page synthese les informations exposees par le backend: dimensions, "
        "repartition des classes, statistiques descriptives et echantillons tabulaires."
    ),
    [
        f"{test_set.get('n_rows', 0):,} lignes test",
        f"{test_set.get('n_features', 0)} features",
        f"{format_percent(test_set.get('anomaly_rate'))} anomalies",
    ],
)

render_metric_cards(
    [
        {
            "label": "Train set",
            "value": f"{train_set.get('n_rows', 0):,}",
            "sub": "jeu d'apprentissage",
            "tone": "accent",
        },
        {
            "label": "Test set",
            "value": f"{test_set.get('n_rows', 0):,}",
            "sub": "jeu d'evaluation",
        },
        {
            "label": "Anomalies",
            "value": f"{test_set.get('n_anomalies', 0):,}",
            "sub": "connexions anormales dans le test set",
            "tone": "danger",
        },
        {
            "label": "Features retenues",
            "value": str(test_set.get("n_features", 0)),
            "sub": source_file,
            "tone": "success",
        },
    ]
)

summary_left, summary_right = st.columns([0.95, 1.05], gap="large")

with summary_left:
    stats_lines = [
        ("Source", source_file),
        ("Train rows", f"{train_set.get('n_rows', 0):,}"),
        ("Test rows", f"{test_set.get('n_rows', 0):,}"),
        ("Features", str(test_set.get("n_features", 0))),
        ("Anomaly rate", format_percent(test_set.get("anomaly_rate"))),
    ]
    stat_markup = "".join(
        f"""
        <div class="stat-line">
            <span class="stat-key">{label}</span>
            <span class="stat-value">{value}</span>
        </div>
        """
        for label, value in stats_lines
    )

    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">Fiche rapide</div>
            <div class="panel-heading">Structure du dataset utilise par l'application</div>
            <p class="panel-copy">
                Les pages de performance et de prediction consomment les memes features
                numeriques preparees dans <code>test_featured.csv</code>. Cela garantit
                une lecture coherente entre exploration, evaluation et inference.
            </p>
            <div class="stat-list" style="margin-top:1rem">
                {stat_markup}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with summary_right:
    tag_markup = "".join(
        f'<span class="tag-pill">{feature}</span>'
        for feature in feature_names
    )
    st.markdown(
        f"""
        <div class="panel">
            <div class="panel-title">Features en entree</div>
            <div class="panel-heading">Variables transmises au backend</div>
            <p class="panel-copy">
                Le front expose un sous-ensemble propre et explicable des variables reseau
                les plus utiles pour la detection d'anomalies.
            </p>
            <div class="tag-cloud" style="margin-top:1rem">
                {tag_markup}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

feature_groups = [
    (
        "Volume et paquets",
        "Mesure l'intensite brute du trafic et les asymetries entre source et destination.",
        ["sbytes", "dbytes", "spkts", "dpkts", "rate"],
    ),
    (
        "Latence et stabilite",
        "Capture les variations de duree, jitter et pertes pour isoler les flux instables.",
        ["dur", "sjit", "djit", "sloss", "dloss"],
    ),
    (
        "Etat reseau",
        "Expose des signaux de transport utiles comme TTL et charge reseau.",
        ["sttl", "dttl", "sload", "dload", "swin", "dwin"],
    ),
    (
        "Contexte recent",
        "Decrit les motifs repetitifs de connexions sur de courtes fenetres temporelles.",
        ["ct_srv_src", "ct_dst_ltm", "ct_src_ltm", "ct_srv_dst"],
    ),
]

tab_classes, tab_groups, tab_distributions, tab_stats, tab_sample = st.tabs(
    ["Classes", "Familles de features", "Distributions", "Statistiques", "Echantillon"]
)

with tab_classes:
    pie_col, bar_col = st.columns(2, gap="large")
    pie_data = label_dist.get("pie_chart", {})

    if pie_data:
        with pie_col:
            fig = go.Figure(
                go.Pie(
                    labels=pie_data["labels"],
                    values=pie_data["values"],
                    hole=0.62,
                    marker=dict(
<<<<<<< HEAD
                        colors=["#2563eb","#dc2626"],
=======
                        colors=[ACCENT, DANGER],
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
                        line=dict(color="#091423", width=3),
                    ),
                    textinfo="percent",
                    textfont=dict(size=13, color="#eef4ff"),
                )
            )
            fig.update_layout(
                **PLOTLY_LAYOUT,
                height=340,
                showlegend=True,
                annotations=[
                    dict(
                        text=f"{test_set.get('n_rows', 0):,}<br><span style='font-size:11px'>lignes</span>",
                        x=0.5,
                        y=0.5,
                        showarrow=False,
                        font=dict(color="#eef4ff", size=15),
                    )
                ],
            )
            st.plotly_chart(fig, use_container_width=True)

        with bar_col:
            fig = go.Figure(
                go.Bar(
                    x=pie_data["labels"],
                    y=pie_data["values"],
                    marker=dict(color=[ACCENT, DANGER]),
                    text=[f"{value:,}" for value in pie_data["values"]],
                    textposition="outside",
                )
            )
            fig.update_layout(
                **PLOTLY_LAYOUT,
                height=340,
                showlegend=False,
                yaxis_title="Nombre de connexions",
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        """
        <div class="callout info">
            Le jeu de test est plus riche en anomalies que la plupart des contextes
            de production reelle. C'est utile pour comparer les modeles, mais cela
            doit rester en tete lors de l'interpretation des scores et du seuil.
        </div>
        """,
        unsafe_allow_html=True,
    )

with tab_groups:
    group_cols = st.columns(2, gap="large")
    for index, (title, copy, tags) in enumerate(feature_groups):
        with group_cols[index % 2]:
            tags_markup = "".join(f'<span class="tag-pill">{tag}</span>' for tag in tags)
            st.markdown(
                f"""
                <div class="panel">
                    <div class="panel-title">Groupe</div>
                    <div class="panel-heading">{title}</div>
                    <p class="panel-copy">{copy}</p>
                    <div class="tag-cloud" style="margin-top:1rem">{tags_markup}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with tab_distributions:
    try:
        dist_data = api_get("/api/dataset/distributions", params={"top_n": 10}, timeout=15)
    except Exception as exc:
        st.markdown(
            f"""
            <div class="callout danger">
                Impossible de recuperer les distributions des features.<br>
                Detail : {explain_api_error(exc)}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        distributions = dist_data.get("distributions", {})
        if not distributions:
            st.info("Aucune distribution n'est disponible.")
        else:
            selected_feature = st.selectbox(
                "Feature a comparer",
                options=list(distributions.keys()),
            )
            feature_payload = distributions[selected_feature]
            normal_values = feature_payload.get("normal", [])
            anomaly_values = feature_payload.get("anomaly", [])

            chart_col, details_col = st.columns([1.15, 0.85], gap="large")

            with chart_col:
                fig = go.Figure()
                fig.add_trace(
                    go.Histogram(
                        x=normal_values,
                        name="Normal",
<<<<<<< HEAD
                        marker_color="#2563eb",
=======
                        marker_color=ACCENT,
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
                        opacity=0.70,
                        nbinsx=45,
                        histnorm="probability density",
                    )
                )
                fig.add_trace(
                    go.Histogram(
                        x=anomaly_values,
                        name="Anomalie",
<<<<<<< HEAD
                        marker_color="#dc2626",
=======
                        marker_color=DANGER,
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
                        opacity=0.60,
                        nbinsx=45,
                        histnorm="probability density",
                    )
                )
                fig.update_layout(
                    **PLOTLY_LAYOUT,
                    barmode="overlay",
                    height=380,
                    title=dict(text=selected_feature, font=dict(color="#eef4ff", size=16)),
                )
                st.plotly_chart(fig, use_container_width=True)

            with details_col:
                normal_stats = feature_payload.get("stats_normal", {})
                anomaly_stats = feature_payload.get("stats_anomaly", {})

                st.markdown(
                    """
                    <div class="panel">
                        <div class="panel-title">Lecture rapide</div>
                        <div class="panel-heading">Comment interpreter la separation</div>
                        <p class="panel-copy">
                            Plus les distributions se decollent entre normal et anomalie,
                            plus la feature a de chances d'aider un modele non supervise.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if normal_stats and anomaly_stats:
                    render_metric_cards(
                        [
                            {
                                "label": "Normal mean",
                                "value": f"{normal_stats.get('mean', 0):.4f}",
                                "sub": f"p95 {normal_stats.get('p95', 0):.4f}",
                                "tone": "accent",
                            },
                            {
                                "label": "Anomalie mean",
                                "value": f"{anomaly_stats.get('mean', 0):.4f}",
                                "sub": f"p95 {anomaly_stats.get('p95', 0):.4f}",
                                "tone": "danger",
                            },
                        ]
                    )

with tab_stats:
    if numeric_stats:
        stats_rows = []
        variability = {}
        for feature, values in numeric_stats.items():
            mean_value = values.get("mean", 0)
            std_value = values.get("std", 0)
            variability[feature] = abs(std_value / (mean_value + 1e-9))
            stats_rows.append(
                {
                    "Feature": feature,
                    "Mean": mean_value,
                    "Std": std_value,
                    "Min": values.get("min", 0),
                    "25%": values.get("25%", 0),
                    "50%": values.get("50%", 0),
                    "75%": values.get("75%", 0),
                    "95%": values.get("95%", 0),
                    "Max": values.get("max", 0),
                }
            )

        stats_df = pd.DataFrame(stats_rows).set_index("Feature")
        st.dataframe(stats_df.style.format("{:.4f}"), use_container_width=True, height=420)

        ordered_variability = dict(
            sorted(variability.items(), key=lambda item: item[1], reverse=True)
        )
        fig = go.Figure(
            go.Bar(
                x=list(ordered_variability.values()),
                y=list(ordered_variability.keys()),
                orientation="h",
                marker=dict(
                    color=list(ordered_variability.values()),
                    colorscale=[[0, "#17324d"], [1, "#5eead4"]],
                ),
            )
        )
        fig.update_layout(
            **PLOTLY_LAYOUT,
            height=520,
            showlegend=False,
            xaxis_title="Coefficient de variation",
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_sample:
    sample_size = st.slider("Nombre de lignes a afficher", min_value=10, max_value=200, value=40, step=10)
    try:
        sample_payload = api_get("/api/dataset/sample", params={"n": sample_size}, timeout=10)
    except Exception as exc:
        st.markdown(
            f"""
            <div class="callout danger">
                Impossible de charger l'echantillon du dataset.<br>
                Detail : {explain_api_error(exc)}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        sample_df = pd.DataFrame(sample_payload.get("sample", []))
        st.dataframe(sample_df, use_container_width=True, height=430, hide_index=True)
        st.markdown(
            f"""
            <div class="callout info">
                Affichage de <strong>{len(sample_df)}</strong> lignes sur
                <strong>{test_set.get('n_rows', 0):,}</strong> dans le jeu de test.
                Les colonnes correspondent aux features reutilisees par les pages
                Performance et Prediction.
            </div>
            """,
            unsafe_allow_html=True,
<<<<<<< HEAD
        )
=======
        )
>>>>>>> e6ce9d0872e163a69c0ca60ee5c2951a91710736
