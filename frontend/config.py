"""
Shared frontend configuration and UI helpers for the Streamlit app.
"""

from __future__ import annotations

import html
import os
from typing import Iterable, Sequence

import requests
import streamlit as st

# Backend
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

# Streamlit page config
PAGE_CONFIG = dict(
    page_title="NetGuard | Network Anomaly Detection",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Navigation
NAV_ITEMS = (
    {
        "key": "home",
        "label": "Accueil",
        "path": "app.py",
        "icon": ":material/space_dashboard:",
        "hint": "Vue d'ensemble du systeme",
    },
    {
        "key": "dataset",
        "label": "Dataset",
        "path": "pages/01_dataset.py",
        "icon": ":material/database:",
        "hint": "Explorer les donnees et les features",
    },
    {
        "key": "performance",
        "label": "Performance",
        "path": "pages/02_performance.py",
        "icon": ":material/monitoring:",
        "hint": "Metriques et visualisations du modele",
    },
    {
        "key": "prediction",
        "label": "Prediction",
        "path": "pages/03_prediction.py",
        "icon": ":material/radar:",
        "hint": "Lancer une inference en temps reel",
    },
)

# Shared colors and chart theme — light design
PALETTE = [
    "#2563eb",
    "#0891b2",
    "#059669",
    "#d97706",
    "#dc2626",
    "#7c3aed",
]
ACCENT  = "#2563eb"
SUCCESS = "#059669"
WARNING = "#d97706"
DANGER  = "#dc2626"
TEXT_MUTED = "#64748b"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#1e293b", size=12),
    margin=dict(l=40, r=20, t=45, b=40),
    xaxis=dict(
        gridcolor="rgba(100,116,139,0.12)",
        linecolor="rgba(100,116,139,0.18)",
        zerolinecolor="rgba(100,116,139,0.18)",
        tickfont=dict(color=TEXT_MUTED, size=10),
    ),
    yaxis=dict(
        gridcolor="rgba(100,116,139,0.12)",
        linecolor="rgba(100,116,139,0.18)",
        zerolinecolor="rgba(100,116,139,0.18)",
        tickfont=dict(color=TEXT_MUTED, size=10),
    ),
    legend=dict(font=dict(color="#1e293b")),
)

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:       #f8fafc;
    --surface:  #ffffff;
    --surface-2:#f1f5f9;
    --border:   rgba(15,23,42,0.10);
    --border-md:rgba(15,23,42,0.16);
    --text:     #0f172a;
    --muted:    #64748b;
    --accent:   #2563eb;
    --accent-bg:#eff6ff;
    --accent-bd:#bfdbfe;
    --success:  #059669;
    --success-bg:#ecfdf5;
    --warning:  #d97706;
    --warning-bg:#fffbeb;
    --danger:   #dc2626;
    --danger-bg:#fef2f2;
    --radius:   14px;
    --radius-lg:20px;
}

html { scroll-behavior: smooth; }

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', sans-serif;
}

[data-testid="stAppViewContainer"] > .main { padding: 0 !important; }
section.main > div { max-width: 1380px; padding-top: 0 !important; }
.block-container { max-width: 1380px; padding: 1rem 1.5rem 3rem; }

#MainMenu, header, footer, [data-testid="stSidebar"], [data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

h1, h2, h3, h4 { font-family: 'Inter', sans-serif; color: var(--text); letter-spacing: -0.02em; }
p, li, label, .stMarkdown, .stText { color: var(--muted); }
code { font-family: 'JetBrains Mono', monospace !important; color: var(--accent) !important; background: var(--accent-bg) !important; padding: 0.1em 0.35em; border-radius: 4px; }

/* Shell */
.shell-meta { color: var(--accent); font-size: 0.68rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; margin-bottom: 0.4rem; }
.shell-panel {
    height: 100%; padding: 1rem 1.15rem;
    border-radius: var(--radius-lg);
    border: 1px solid var(--border);
    background: var(--surface);
    box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04);
}
.shell-divider { border: none; border-top: 1px solid var(--border); margin: 0.6rem 0 1.4rem; }

/* Brand */
.brand-lockup { display: flex; align-items: center; gap: 0.8rem; min-height: 48px; }
.brand-mark {
    width: 48px; height: 48px; border-radius: 14px;
    display: inline-flex; align-items: center; justify-content: center;
    background: var(--accent);
    color: #ffffff;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem; font-weight: 600; letter-spacing: 0.06em;
    box-shadow: 0 4px 12px rgba(37,99,235,0.30);
}
.brand-copy { display: flex; flex-direction: column; gap: 0.15rem; }
.brand-name { color: var(--text); font-size: 1rem; font-weight: 600; }
.brand-meta { color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.12em; }
.brand-badge {
    display: inline-flex; align-items: center;
    margin-top: 0.75rem; padding: 0.28rem 0.65rem;
    border-radius: 999px; border: 1px solid var(--accent-bd);
    background: var(--accent-bg);
    color: var(--accent); font-size: 0.72rem; font-family: 'JetBrains Mono', monospace;
}

/* Nav */
.nav-helper { margin: 0.1rem 0 0.8rem; color: var(--muted); font-size: 0.82rem; line-height: 1.6; }
div[data-testid="stPageLink"] { width: 100%; }
a[data-testid="stPageLink-NavLink"] {
    width: 100% !important; min-height: 56px;
    border-radius: var(--radius) !important;
    border: 1px solid var(--border) !important;
    background: var(--surface) !important;
    color: var(--muted) !important;
    font-size: 0.84rem !important; font-weight: 500 !important;
    transition: border-color 0.15s, background 0.15s;
}
a[data-testid="stPageLink-NavLink"]:hover {
    border-color: var(--accent-bd) !important;
    background: var(--accent-bg) !important;
    color: var(--accent) !important;
}

/* Status chip */
.status-chip {
    display: inline-flex; align-items: center; gap: 0.4rem;
    padding: 0.3rem 0.7rem; border-radius: 999px;
    font-size: 0.76rem; font-weight: 500; border: 1px solid; margin-bottom: 0.55rem;
}
.status-chip.ok   { border-color: #a7f3d0; background: var(--success-bg); color: var(--success); }
.status-chip.warn { border-color: #fca5a5; background: var(--danger-bg);  color: var(--danger); }
.status-chip-dot  { width: 6px; height: 6px; border-radius: 50%; background: currentColor; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.status-copy { color: var(--muted); font-size: 0.77rem; line-height: 1.5; margin: 0; }

/* Hero */
.hero-panel {
    padding: 2rem 2.2rem; border-radius: var(--radius-lg);
    border: 1px solid var(--border); background: var(--surface);
    box-shadow: 0 1px 3px rgba(15,23,42,0.06);
    margin-bottom: 1.2rem; position: relative; overflow: hidden;
}
.hero-panel::before {
    content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
    background: linear-gradient(90deg, var(--accent), #0891b2 60%, transparent);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}
.hero-grid { display: grid; grid-template-columns: 1fr auto; gap: 1.8rem; align-items: start; }
.hero-eyebrow { color: var(--accent); font-size: 0.7rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; margin-bottom: 0.5rem; }
.hero-title { font-size: 2.2rem; font-weight: 700; letter-spacing: -0.03em; color: var(--text); margin: 0 0 0.6rem; line-height: 1.2; }
.hero-copy { color: var(--muted); font-size: 0.93rem; line-height: 1.65; max-width: 640px; margin: 0; }
.hero-summary { background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem 1.2rem; min-width: 200px; }
.hero-summary-label { color: var(--accent); font-size: 0.64rem; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 0.7rem; }
.hero-summary-list { display: flex; flex-direction: column; gap: 0.5rem; }
.hero-summary-item { display: flex; align-items: flex-start; gap: 0.5rem; }
.hero-summary-index { font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; font-weight: 500; color: var(--accent); min-width: 20px; padding-top: 0.05rem; }
.hero-summary-text { color: var(--text); font-size: 0.8rem; line-height: 1.45; }
.chip-row { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 1.2rem; }
.chip { padding: 0.24rem 0.65rem; border-radius: 999px; border: 1px solid var(--accent-bd); background: var(--accent-bg); color: var(--accent); font-size: 0.73rem; font-weight: 500; }

/* Metric cards */
.metric-card { padding: 1rem 1.1rem; border-radius: var(--radius); border: 1px solid var(--border); background: var(--surface); }
.metric-card.accent  { border-left: 3px solid var(--accent);  }
.metric-card.success { border-left: 3px solid var(--success); }
.metric-card.danger  { border-left: 3px solid var(--danger);  }
.metric-label { color: var(--muted); font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.3rem; }
.metric-value { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text); line-height: 1.1; }
.metric-value.accent  { color: var(--accent); }
.metric-value.success { color: var(--success); }
.metric-value.danger  { color: var(--danger); }
.metric-sub { color: var(--muted); font-size: 0.72rem; margin-top: 0.25rem; }

/* Panel */
.panel { padding: 1.2rem 1.3rem; border-radius: var(--radius); border: 1px solid var(--border); background: var(--surface); margin-bottom: 1rem; }
.panel-title { color: var(--accent); font-size: 0.66rem; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 0.35rem; }
.panel-heading { color: var(--text); font-size: 1rem; font-weight: 600; margin-bottom: 0.4rem; }
.panel-copy { color: var(--muted); font-size: 0.85rem; line-height: 1.6; margin: 0; }

/* Stat list */
.stat-list { display: flex; flex-direction: column; gap: 0; }
.stat-line { display: flex; align-items: center; justify-content: space-between; padding: 0.38rem 0; border-bottom: 1px solid var(--border); }
.stat-line:last-child { border-bottom: none; }
.stat-key { color: var(--muted); font-size: 0.82rem; }
.stat-value { color: var(--text); font-size: 0.82rem; font-weight: 500; font-family: 'JetBrains Mono', monospace; }

/* Tag cloud */
.tag-cloud { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.tag-pill { padding: 0.2rem 0.55rem; border-radius: 999px; border: 1px solid var(--border-md); background: var(--surface-2); color: var(--text); font-size: 0.73rem; font-weight: 500; }

/* Callouts */
.callout { padding: 0.8rem 1rem; border-radius: var(--radius); font-size: 0.85rem; line-height: 1.6; margin-bottom: 1rem; border: 1px solid; }
.callout.info    { border-color: var(--accent-bd); background: var(--accent-bg);  color: #1d4ed8; }
.callout.warn    { border-color: #fed7aa; background: var(--warning-bg); color: #92400e; }
.callout.danger  { border-color: #fecaca; background: var(--danger-bg);  color: #991b1b; }
.callout.success { border-color: #a7f3d0; background: var(--success-bg); color: #065f46; }

/* Quick cards */
.quick-card { padding: 1.2rem 1.3rem; border-radius: var(--radius); border: 1px solid var(--border); background: var(--surface); height: 100%; margin-bottom: 0.8rem; transition: border-color 0.15s, box-shadow 0.15s; }
.quick-card:hover { border-color: var(--accent-bd); box-shadow: 0 4px 12px rgba(37,99,235,0.08); }
.quick-card-title { color: var(--text); font-size: 0.96rem; font-weight: 600; margin-bottom: 0.4rem; }
.quick-card-copy { color: var(--muted); font-size: 0.83rem; line-height: 1.56; margin-bottom: 0.7rem; }

/* Section headings */
.section-kicker { color: var(--accent); font-size: 0.66rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; margin-bottom: 0.25rem; }
.section-heading { color: var(--text); font-size: 1.22rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0.85rem; }

/* Ranking rows */
.ranking-row { display: grid; grid-template-columns: 48px 1fr auto; gap: 1rem; align-items: center; padding: 0.85rem 1rem; border-radius: var(--radius); border: 1px solid var(--border); background: var(--surface); margin-bottom: 0.5rem; transition: border-color 0.15s; }
.ranking-row.active { border-color: var(--accent-bd); background: var(--accent-bg); }
.ranking-rank { font-family: 'JetBrains Mono', monospace; font-size: 1.2rem; font-weight: 600; color: var(--muted); text-align: center; }
.ranking-name { color: var(--text); font-size: 0.88rem; font-weight: 600; margin-bottom: 0.18rem; }
.ranking-meta { color: var(--muted); font-size: 0.74rem; margin-bottom: 0.35rem; font-family: 'JetBrains Mono', monospace; }
.ranking-track { height: 4px; border-radius: 999px; background: var(--surface-2); overflow: hidden; }
.ranking-fill { height: 100%; border-radius: 999px; background: var(--accent); }
.ranking-score { font-family: 'JetBrains Mono', monospace; font-size: 1rem; font-weight: 600; color: var(--accent); text-align: right; min-width: 56px; }

/* Score bars */
.score-row { display: grid; grid-template-columns: 140px 32px 1fr 64px; gap: 0.55rem; align-items: center; padding: 0.4rem 0; }
.score-name { color: var(--text); font-size: 0.83rem; font-weight: 500; }
.score-weight { color: var(--muted); font-size: 0.71rem; font-family: 'JetBrains Mono', monospace; }
.score-track { height: 6px; border-radius: 999px; background: var(--surface-2); overflow: hidden; }
.score-fill { height: 100%; border-radius: 999px; transition: width 0.4s; }
.score-value { font-family: 'JetBrains Mono', monospace; font-size: 0.81rem; font-weight: 500; text-align: right; }

/* Result banner */
.result-banner { padding: 1.3rem 1.4rem; border-radius: var(--radius); border: 1px solid; margin-bottom: 0.85rem; }
.result-banner.danger  { border-color: #fecaca; background: var(--danger-bg); }
.result-banner.success { border-color: #a7f3d0; background: var(--success-bg); }
.result-tag { font-size: 0.64rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted); margin-bottom: 0.35rem; }
.result-title.danger  { font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; color: var(--danger); margin-bottom: 0.18rem; }
.result-title.success { font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; color: var(--success); margin-bottom: 0.18rem; }
.result-title { font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; color: var(--text); margin-bottom: 0.18rem; }
.result-copy { color: var(--muted); font-size: 0.84rem; font-family: 'JetBrains Mono', monospace; }

/* Helper note */
.helper-note { font-size: 0.79rem; color: var(--muted); line-height: 1.6; padding: 0.65rem 0.85rem; border-radius: var(--radius); background: var(--surface-2); border: 1px solid var(--border); margin-top: 0.7rem; }

/* Streamlit widget overrides */
[data-testid="stButton"] > button {
    border-radius: var(--radius) !important; font-weight: 500 !important;
    font-size: 0.85rem !important; border: 1px solid var(--border-md) !important;
    background: var(--surface) !important; color: var(--text) !important;
    transition: all 0.15s !important;
}
[data-testid="stButton"] > button:hover { border-color: var(--accent-bd) !important; background: var(--accent-bg) !important; color: var(--accent) !important; }
[data-testid="stButton"] > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    border-color: #3b82f6 !important;
    background: #3b82f6 !important;
    color: #ffffff !important;
    font-weight: 600 !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover { background: #2563eb !important; border-color: #2563eb !important; }

[data-testid="stTabs"] [data-baseweb="tab-list"] { background: var(--surface-2) !important; border-radius: var(--radius) !important; padding: 0.25rem !important; gap: 0.15rem !important; border: 1px solid var(--border) !important; }
[data-testid="stTabs"] [data-baseweb="tab"] { border-radius: 10px !important; color: var(--muted) !important; font-weight: 500 !important; font-size: 0.85rem !important; }
[data-testid="stTabs"] [aria-selected="true"] { background: var(--surface) !important; color: var(--text) !important; box-shadow: 0 1px 3px rgba(15,23,42,0.08) !important; }

[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"] {
    border-radius: var(--radius) !important; border-color: var(--border-md) !important;
    background: var(--surface) !important; color: var(--text) !important;
    font-family: 'JetBrains Mono', monospace !important;
}
[data-testid="stNumberInput"] input:focus,
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}
label[data-testid="stWidgetLabel"] { color: var(--muted) !important; font-size: 0.81rem !important; font-weight: 500 !important; }
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] { border-color: var(--accent) !important; background: var(--accent) !important; }

[data-testid="stDataFrame"] { border-radius: var(--radius) !important; overflow: hidden; border: 1px solid var(--border) !important; }

.js-plotly-plot .plotly, .js-plotly-plot .plotly svg { background: transparent !important; }

@media (max-width: 980px) {
    .block-container { padding: 1rem 1rem 2rem; }
    .hero-title { font-size: 1.75rem; }
    .hero-grid { grid-template-columns: 1fr; }
    .score-row { grid-template-columns: 1fr; gap: 0.3rem; }
    .ranking-row { grid-template-columns: 1fr; }
}
</style>
"""


@st.cache_data(ttl=20, show_spinner=False)
def get_backend_health() -> bool:
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=2)
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False


@st.cache_data(ttl=300, show_spinner=False)
def api_get(path: str, params: dict | None = None, timeout: int = 30):
    response = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict, timeout: int = 15):
    response = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def explain_api_error(exc: Exception) -> str:
    if isinstance(exc, requests.ConnectionError):
        return (
            f"Backend inaccessible sur {BACKEND_URL}. Lance l'API avec "
            "`python backend/main.py` depuis la racine du projet ou "
            "`python main.py` depuis le dossier `backend`, puis recharge la page."
        )
    if isinstance(exc, requests.Timeout):
        return (
            f"Le backend sur {BACKEND_URL} ne repond pas avant le delai imparti. "
            "Verifie que l'API est bien demarree."
        )
    if isinstance(exc, requests.HTTPError):
        status_code = exc.response.status_code if exc.response is not None else "?"
        return f"Le backend a repondu avec HTTP {status_code} sur {BACKEND_URL}."
    return str(exc)


def format_percent(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    numeric = float(value)
    if abs(numeric) <= 1:
        numeric *= 100
    return f"{numeric:.{digits}f}%"


def format_number(value: float | int | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    return f"{float(value):.{digits}f}"


def render_app_shell(active_page: str) -> None:
    st.markdown(STYLE, unsafe_allow_html=True)

    current_item = next((item for item in NAV_ITEMS if item["key"] == active_page), NAV_ITEMS[0])
    brand_col, nav_col, status_col = st.columns([2.25, 5.5, 2.25], gap="medium")

    with brand_col:
        st.markdown(
            """
            <div class="shell-panel">
                <div class="shell-meta">Control Deck</div>
                <div class="brand-lockup">
                    <div class="brand-mark">NG</div>
                    <div class="brand-copy">
                        <div class="brand-name">NetGuard</div>
                        <div class="brand-meta">Network anomaly intelligence</div>
                    </div>
                </div>
                <div class="brand-badge">UNSW-NB15 · anomaly command center</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with nav_col:
        st.markdown(
            f"""
            <div class="shell-meta">Navigation rapide</div>
            <div class="nav-helper">
                Vous etes sur <strong>{html.escape(current_item["label"])}</strong>.
                Passez d'une vue a l'autre sans perdre le contexte du dashboard.
            </div>
            """,
            unsafe_allow_html=True,
        )
        button_cols = st.columns(len(NAV_ITEMS), gap="small")
        for col, item in zip(button_cols, NAV_ITEMS):
            with col:
                nav_label = f"**{item['label']}**" if item["key"] == active_page else item["label"]
                st.page_link(
                    item["path"],
                    label=nav_label,
                    icon=item["icon"],
                    help=item["hint"],
                    use_container_width=True,
                )

    with status_col:
        is_online = get_backend_health()
        state_class = "ok" if is_online else "warn"
        state_label = "API disponible" if is_online else "API indisponible"
        status_copy = (
            "Toutes les visualisations et predictions sont synchronisees avec le backend."
            if is_online
            else "Le shell reste navigable, mais les vues dependantes de l'API afficheront une erreur."
        )
        st.markdown(
            f"""
            <div class="shell-panel">
                <div class="shell-meta">Etat backend</div>
                <div class="status-chip {state_class}">
                    <span class="status-chip-dot"></span>
                    <span>{html.escape(state_label)}</span>
                </div>
                <p class="status-copy">{html.escape(status_copy)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="shell-divider">', unsafe_allow_html=True)


def render_page_header(
    eyebrow: str,
    title: str,
    description: str,
    badges: Iterable[str] | None = None,
) -> None:
    badge_values = [str(b) for b in (badges or []) if str(b).strip()]
    badge_markup = "".join(f'<span class="chip">{html.escape(b)}</span>' for b in badge_values)

    summary_items_markup = "".join(
        (
            '<div class="hero-summary-item">'
            f'<span class="hero-summary-index">{i:02d}</span>'
            f'<div class="hero-summary-text">{html.escape(b)}</div>'
            "</div>"
        )
        for i, b in enumerate(badge_values[:3], start=1)
    )
    summary_markup = (
        '<aside class="hero-summary">'
        '<div class="hero-summary-label">Contexte direct</div>'
        f'<div class="hero-summary-list">{summary_items_markup}</div>'
        "</aside>"
    ) if summary_items_markup else ""

    st.markdown(
        '<section class="hero-panel">'
        '<div class="hero-grid">'
        "<div>"
        f'<div class="hero-eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1 class="hero-title">{html.escape(title)}</h1>'
        f'<p class="hero-copy">{html.escape(description)}</p>'
        "</div>"
        f"{summary_markup}"
        "</div>"
        f'<div class="chip-row">{badge_markup}</div>'
        "</section>",
        unsafe_allow_html=True,
    )


def render_metric_cards(cards: Sequence[dict]) -> None:
    if not cards:
        return
    columns = st.columns(len(cards), gap="small")
    for column, card in zip(columns, cards):
        tone = card.get("tone", "")
        value_class = tone if tone in {"accent", "success", "warning", "danger"} else ""
        with column:
            st.markdown(
                f"""
                <div class="metric-card {html.escape(tone)}">
                    <div class="metric-label">{html.escape(str(card.get("label", "")))}</div>
                    <div class="metric-value {html.escape(value_class)}">
                        {html.escape(str(card.get("value", "-")))}
                    </div>
                    <div class="metric-sub">{html.escape(str(card.get("sub", "")))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )