"""Shared Streamlit configuration, API helpers, and dark UI components."""

from __future__ import annotations

import html
import os
from typing import Iterable, Sequence

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

PAGE_CONFIG = dict(
    page_title="NetGuard | Network Anomaly Detection",
    layout="wide",
    initial_sidebar_state="collapsed",
)

NAV_ITEMS = (
    {
        "key": "home",
        "label": "Overview",
        "path": "app.py",
        "icon": ":material/dashboard:",
    },
    {
        "key": "dataset",
        "label": "Dataset",
        "path": "pages/01_dataset.py",
        "icon": ":material/database:",
    },
    {
        "key": "performance",
        "label": "Performance",
        "path": "pages/02_performance.py",
        "icon": ":material/monitoring:",
    },
    {
        "key": "prediction",
        "label": "Prediction",
        "path": "pages/03_prediction.py",
        "icon": ":material/radar:",
    },
)

PALETTE = ["#38bdf8", "#22c55e", "#f59e0b", "#fb7185", "#a78bfa", "#14b8a6"]
ACCENT = "#38bdf8"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
DANGER = "#fb7185"
VIOLET = "#a78bfa"
TEXT = "#e5edf7"
TEXT_MUTED = "#94a3b8"
BORDER = "rgba(148, 163, 184, 0.18)"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color=TEXT, size=12),
    margin=dict(l=44, r=20, t=46, b=42),
    xaxis=dict(
        gridcolor="rgba(148,163,184,0.14)",
        linecolor="rgba(148,163,184,0.18)",
        zerolinecolor="rgba(148,163,184,0.18)",
        tickfont=dict(color=TEXT_MUTED, size=10),
    ),
    yaxis=dict(
        gridcolor="rgba(148,163,184,0.14)",
        linecolor="rgba(148,163,184,0.18)",
        zerolinecolor="rgba(148,163,184,0.18)",
        tickfont=dict(color=TEXT_MUTED, size=10),
    ),
    legend=dict(font=dict(color=TEXT), orientation="h", yanchor="bottom", y=1.02, x=0),
)

STYLE = """
<style>
:root {
    --bg: #070b12;
    --bg-soft: #0b111c;
    --surface: #0f1724;
    --surface-2: #121c2b;
    --surface-3: #172235;
    --border: rgba(148, 163, 184, 0.18);
    --border-strong: rgba(148, 163, 184, 0.28);
    --text: #e5edf7;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --success: #22c55e;
    --warning: #f59e0b;
    --danger: #fb7185;
    --violet: #a78bfa;
    --radius: 8px;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    color: var(--text);
    font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

[data-testid="stAppViewContainer"] > .main { padding: 0 !important; }
.block-container { max-width: 1360px; padding: 1rem 1.35rem 3rem; }
#MainMenu, footer, [data-testid="stSidebar"], [data-testid="stSidebarNav"],
[data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; }

h1, h2, h3, h4, h5, h6 { color: var(--text); letter-spacing: 0; }
p, li, label, .stMarkdown { color: var(--muted); }
code {
    color: var(--accent) !important;
    background: rgba(56,189,248,0.10) !important;
    border: 1px solid rgba(56,189,248,0.18);
    border-radius: 4px;
    padding: 0.08rem 0.28rem;
}

.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.8rem 0.95rem;
    margin-bottom: 0.95rem;
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: var(--radius);
}
.brand { display: flex; align-items: center; gap: 0.7rem; min-width: 220px; }
.brand-mark {
    width: 38px; height: 38px;
    display: inline-flex; align-items: center; justify-content: center;
    border-radius: 8px;
    background: #111d2e;
    border: 1px solid rgba(56,189,248,0.38);
    color: var(--accent);
    font-weight: 800;
    font-size: 0.78rem;
    letter-spacing: 0;
}
.brand-name { color: var(--text); font-weight: 700; font-size: 0.98rem; line-height: 1.1; }
.brand-sub { color: var(--muted); font-size: 0.72rem; margin-top: 0.12rem; }
.nav-row { display: flex; gap: 0.45rem; flex-wrap: wrap; justify-content: flex-end; }
div[data-testid="stPageLink"] { display: inline-flex; width: auto; }
a[data-testid="stPageLink-NavLink"] {
    min-height: 38px;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    background: var(--surface-2) !important;
    color: var(--muted) !important;
    padding: 0.2rem 0.7rem !important;
}
a[data-testid="stPageLink-NavLink"]:hover {
    border-color: rgba(56,189,248,0.45) !important;
    color: var(--text) !important;
    background: #132033 !important;
}

.page-head {
    padding: 1.25rem 1.35rem;
    margin-bottom: 1rem;
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    background: var(--surface);
    border-radius: var(--radius);
}
.eyebrow {
    color: var(--accent);
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 0.35rem;
}
.page-title { color: var(--text); font-size: 1.85rem; line-height: 1.16; font-weight: 800; margin: 0; }
.page-copy { color: var(--muted); font-size: 0.92rem; line-height: 1.55; max-width: 780px; margin: 0.55rem 0 0; }
.badge-row { display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.9rem; }
.badge {
    color: var(--text);
    border: 1px solid var(--border);
    background: var(--surface-2);
    border-radius: 999px;
    padding: 0.23rem 0.62rem;
    font-size: 0.73rem;
}

.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.75rem;
    margin-bottom: 1rem;
}
.metric-card {
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: var(--radius);
    padding: 0.92rem;
    min-height: 116px;
}
.metric-card.accent { border-top: 2px solid var(--accent); }
.metric-card.success { border-top: 2px solid var(--success); }
.metric-card.warning { border-top: 2px solid var(--warning); }
.metric-card.danger { border-top: 2px solid var(--danger); }
.metric-label {
    color: var(--muted);
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
.metric-value {
    color: var(--text);
    font-size: 1.7rem;
    font-weight: 800;
    line-height: 1.1;
    margin-top: 0.25rem;
    overflow-wrap: anywhere;
}
.metric-sub { color: var(--muted); font-size: 0.74rem; line-height: 1.35; margin-top: 0.28rem; }

.panel {
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1rem;
    margin-bottom: 0.9rem;
}
.panel-title {
    color: var(--accent);
    font-size: 0.67rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.35rem;
}
.panel-heading { color: var(--text); font-size: 1rem; font-weight: 750; margin-bottom: 0.35rem; }
.panel-copy { color: var(--muted); font-size: 0.85rem; line-height: 1.55; margin: 0; }

.kv-list { display: flex; flex-direction: column; gap: 0; margin-top: 0.75rem; }
.kv-line {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.45rem 0;
    border-bottom: 1px solid var(--border);
}
.kv-line:last-child { border-bottom: none; }
.kv-key { color: var(--muted); font-size: 0.8rem; }
.kv-value { color: var(--text); font-size: 0.8rem; font-weight: 650; text-align: right; overflow-wrap: anywhere; }

.callout {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface-2);
    padding: 0.78rem 0.9rem;
    margin-bottom: 0.9rem;
    color: var(--muted);
    font-size: 0.84rem;
    line-height: 1.5;
}
.callout.info { border-color: rgba(56,189,248,0.30); }
.callout.success { border-color: rgba(34,197,94,0.32); color: #bbf7d0; }
.callout.warning { border-color: rgba(245,158,11,0.35); color: #fde68a; }
.callout.danger { border-color: rgba(251,113,133,0.35); color: #fecdd3; }

.tag-cloud { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.75rem; }
.tag {
    border: 1px solid var(--border);
    background: var(--surface-2);
    color: var(--text);
    border-radius: 999px;
    padding: 0.18rem 0.5rem;
    font-size: 0.72rem;
}

.rank-row {
    display: grid;
    grid-template-columns: 38px 1fr 70px;
    gap: 0.75rem;
    align-items: center;
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: var(--radius);
    padding: 0.7rem 0.75rem;
    margin-bottom: 0.5rem;
}
.rank-row:first-child { border-color: rgba(34,197,94,0.38); }
.rank-index { color: var(--muted); font-weight: 800; text-align: center; }
.rank-name { color: var(--text); font-size: 0.86rem; font-weight: 750; }
.rank-meta { color: var(--muted); font-size: 0.72rem; margin-top: 0.16rem; }
.rank-track { height: 5px; border-radius: 999px; background: var(--surface-3); overflow: hidden; margin-top: 0.42rem; }
.rank-fill { height: 100%; background: var(--accent); border-radius: 999px; }
.rank-score { color: var(--accent); font-weight: 800; text-align: right; }

.score-row {
    display: grid;
    grid-template-columns: 100px 1fr 58px;
    align-items: center;
    gap: 0.55rem;
    margin: 0.42rem 0;
}
.score-name { color: var(--text); font-size: 0.8rem; }
.score-track { height: 7px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
.score-fill { height: 100%; border-radius: 999px; background: var(--accent); }
.score-value { color: var(--text); font-size: 0.78rem; font-weight: 700; text-align: right; }

.result {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--surface);
    padding: 1rem;
    margin-bottom: 0.9rem;
}
.result.danger { border-color: rgba(251,113,133,0.45); }
.result.success { border-color: rgba(34,197,94,0.42); }
.result-kicker { color: var(--muted); font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }
.result-title { font-size: 1.65rem; font-weight: 850; margin-top: 0.18rem; color: var(--text); }
.result-title.danger { color: var(--danger); }
.result-title.success { color: var(--success); }
.result-meta { color: var(--muted); font-size: 0.82rem; margin-top: 0.25rem; }

div[data-testid="stTabs"] button { color: var(--muted) !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: var(--accent) !important; }
div[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }

.stButton > button {
    border-radius: 8px;
    border: 1px solid rgba(56,189,248,0.38);
    background: #132033;
    color: var(--text);
    min-height: 42px;
    font-weight: 700;
}
.stButton > button:hover {
    border-color: var(--accent);
    color: white;
}

@media (max-width: 900px) {
    .topbar { align-items: flex-start; flex-direction: column; }
    .nav-row { justify-content: flex-start; }
    .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .page-title { font-size: 1.45rem; }
}
@media (max-width: 560px) {
    .metric-grid { grid-template-columns: 1fr; }
    .rank-row { grid-template-columns: 30px 1fr; }
    .rank-score { grid-column: 2; text-align: left; }
}
</style>
"""


def api_get(path: str, params: dict | None = None, timeout: int = 15) -> dict:
    response = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict, timeout: int = 30) -> dict:
    response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def explain_api_error(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except Exception:
            detail = exc.response.text
        return f"{exc.response.status_code}: {detail}"
    if isinstance(exc, requests.ConnectionError):
        return f"Backend unreachable at {BACKEND_URL}"
    if isinstance(exc, requests.Timeout):
        return "Backend request timed out"
    return str(exc)


def escape(value: object) -> str:
    return html.escape(str(value))


def format_number(value: object, digits: int = 4) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return escape(value)
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def format_percent(value: object, digits: int = 1) -> str:
    if value in (None, ""):
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return escape(value)
    return f"{number:.{digits}f}%"


def render_app_shell(active_key: str) -> None:
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="topbar">
            <div class="brand">
                <div class="brand-mark">NG</div>
                <div>
                    <div class="brand-name">NetGuard</div>
                    <div class="brand-sub">Anomaly detection operations</div>
                </div>
            </div>
            <div class="nav-row">
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(len(NAV_ITEMS), gap="small")
    for col, item in zip(cols, NAV_ITEMS):
        with col:
            st.page_link(
                item["path"],
                label=item["label"],
                icon=item["icon"],
                disabled=item["key"] == active_key,
            )
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_page_header(
    title: str,
    subtitle: str,
    copy: str = "",
    badges: Iterable[str] | None = None,
) -> None:
    badge_markup = ""
    if badges:
        badge_markup = '<div class="badge-row">' + "".join(
            f'<span class="badge">{escape(badge)}</span>' for badge in badges if badge
        ) + "</div>"
    copy_markup = f'<p class="page-copy">{escape(copy)}</p>' if copy else ""
    st.markdown(
        (
            '<div class="page-head">'
            f'<div class="eyebrow">{escape(subtitle)}</div>'
            f'<h1 class="page-title">{escape(title)}</h1>'
            f"{copy_markup}"
            f"{badge_markup}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_metric_cards(cards: Sequence[dict]) -> None:
    cards_markup = "".join(
        (
            f'<div class="metric-card {escape(card.get("tone", ""))}">'
            f'<div class="metric-label">{escape(card.get("label", ""))}</div>'
            f'<div class="metric-value">{escape(card.get("value", "-"))}</div>'
            f'<div class="metric-sub">{escape(card.get("sub", ""))}</div>'
            "</div>"
        )
        for card in cards
    )
    st.markdown(f'<div class="metric-grid">{cards_markup}</div>', unsafe_allow_html=True)


def render_callout(message: str, tone: str = "info") -> None:
    st.markdown(
        f'<div class="callout {escape(tone)}">{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def render_kv_panel(title: str, heading: str, rows: Sequence[tuple[str, object]]) -> None:
    row_markup = "".join(
        (
            '<div class="kv-line">'
            f'<span class="kv-key">{escape(key)}</span>'
            f'<span class="kv-value">{escape(value)}</span>'
            "</div>"
        )
        for key, value in rows
    )
    st.markdown(
        (
            '<div class="panel">'
            f'<div class="panel-title">{escape(title)}</div>'
            f'<div class="panel-heading">{escape(heading)}</div>'
            f'<div class="kv-list">{row_markup}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_tags(tags: Iterable[str]) -> None:
    tag_markup = "".join(f'<span class="tag">{escape(tag)}</span>' for tag in tags)
    st.markdown(f'<div class="tag-cloud">{tag_markup}</div>', unsafe_allow_html=True)


def render_ranking(metrics: Sequence[dict], score_key: str = "perf_score", limit: int = 6) -> None:
    rows = []
    max_score = max((float(item.get(score_key, 0) or 0) for item in metrics), default=1.0)
    max_score = max(max_score, 1e-9)
    for idx, item in enumerate(metrics[:limit], start=1):
        score = float(item.get(score_key, 0) or 0)
        width = max(2.0, 100 * score / max_score)
        rows.append(
            (
                '<div class="rank-row">'
                f'<div class="rank-index">{idx}</div>'
                "<div>"
                f'<div class="rank-name">{escape(item.get("model", "Model"))}</div>'
                f'<div class="rank-meta">F1 {format_number(item.get("f1"))} | AUC {format_number(item.get("roc_auc"))}</div>'
                f'<div class="rank-track"><div class="rank-fill" style="width:{width:.1f}%"></div></div>'
                "</div>"
                f'<div class="rank-score">{format_number(score)}</div>'
                "</div>"
            )
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def render_score_bars(scores: dict[str, float], colors: dict[str, str] | None = None) -> None:
    colors = colors or {}
    rows = []
    for name, value in scores.items():
        val = max(0.0, min(float(value or 0), 1.0))
        color = colors.get(name, ACCENT)
        rows.append(
            (
                '<div class="score-row">'
                f'<div class="score-name">{escape(name)}</div>'
                f'<div class="score-track"><div class="score-fill" style="width:{val * 100:.1f}%; background:{color};"></div></div>'
                f'<div class="score-value">{val:.3f}</div>'
                "</div>"
            )
        )
    st.markdown("".join(rows), unsafe_allow_html=True)
