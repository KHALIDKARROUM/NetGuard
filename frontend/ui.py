"""Reusable, escaped UI components. Interactive controls remain native Streamlit."""
from __future__ import annotations
import html
import math
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Sequence
import streamlit as st
from api import api_get
from theme import ACCENT

NAV_ITEMS = (
    ("home", "Overview", "app.py", ":material/space_dashboard:"),
    ("dataset", "Dataset explorer", "pages/01_dataset.py", ":material/database:"),
    ("performance", "Model performance", "pages/02_performance.py", ":material/monitoring:"),
    ("prediction", "Prediction lab", "pages/03_prediction.py", ":material/radar:"),
)
ICON_PATHS = {
    "shield": '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    "layers": '<path d="m12 3 10 6-10 6L2 9l10-6Zm-10 12 10 6 10-6M2 12l10 6 10-6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
    "alert": '<path d="m12 3 10 18H2L12 3Zm0 6v5m0 3v1"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "upload": '<path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/>',
}

def escape(value: object) -> str:
    return html.escape(str(value))

def icon(name: str, size: int = 20) -> str:
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON_PATHS.get(name, ICON_PATHS["activity"])}</svg>'

@contextmanager
def panel():
    """Mark native containers so their surface works across Streamlit versions."""
    with st.container(border=True):
        st.markdown('<span class="panel-marker"></span>', unsafe_allow_html=True)
        yield

def format_number(value: object, digits: int = 3) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:,.0f}" if abs(number) >= 1000 else f"{number:.{digits}f}".rstrip("0").rstrip(".")

def format_percent(value: object, digits: int = 1) -> str:
    """Format percentage-point values, such as the dataset's anomaly_rate."""
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.{digits}f}%" if math.isfinite(number) else "—"

def format_rate(value: object, digits: int = 1) -> str:
    """Format 0–1 metric fractions without confusing them with percentages."""
    return "—" if value is None or value == "" else format_percent(float(value) * 100, digits)

def render_app_shell(active_key: str) -> dict | None:
    css = Path(__file__).with_name("styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(f'<div class="brand"><span class="brand-mark">{icon("shield", 25)}</span><div class="brand-name">NetGuard<span>NETWORK INTELLIGENCE</span></div></div><div class="workspace-chip"><span class="workspace-icon">N</span><div>Research workspace<small>UNSW-NB15 dataset</small></div></div><div class="nav-label">WORKSPACE</div>', unsafe_allow_html=True)
        for key, label, path, material_icon in NAV_ITEMS:
            st.page_link(path, label=label, icon=material_icon, disabled=key == active_key)
        st.markdown(f'<div class="sidebar-note"><span class="sidebar-note-icon">{icon("shield", 23)}</span><strong>Understand your traffic.</strong><p>Explore the data, evaluate your model, and investigate connections.</p><span class="sidebar-tag">Supervised detection</span></div>', unsafe_allow_html=True)
        try:
            health = api_get("/health", timeout=3)
        except Exception:
            health = None
        online = bool(health and health.get("status") == "ok")
        st.markdown(f'<div class="service-status"><span class="status-dot {"online" if online else "offline"}"></span><div>{"Analysis service online" if online else "Analysis service offline"}<small>{"Saved model ready" if online else "Waiting for backend"}</small></div></div><div class="sidebar-footer">NetGuard <span>Research edition</span></div>', unsafe_allow_html=True)
    label = next((label for key, label, *_ in NAV_ITEMS if key == active_key), "Overview")
    left, right = st.columns([5, 1])
    with left:
        st.markdown(f'<div class="context-bar">Workspace <span>/</span> <strong>{escape(label)}</strong></div>', unsafe_allow_html=True)
    with right:
        if st.button("Refresh data", key=f"refresh_{active_key}", help="Reload service status and analysis data.", use_container_width=True):
            api_get.clear()
            st.rerun()
    return health

def render_page_header(title: str, subtitle: str, copy: str = "", badges: Iterable[str] | None = None) -> None:
    badge_markup = "".join(f'<span class="badge">{escape(b)}</span>' for b in (badges or []) if b)
    st.markdown(f'<div class="page-head"><div class="eyebrow">{escape(subtitle)}</div><h1>{escape(title)}</h1><p>{escape(copy)}</p>{f"<div class=badge-row>{badge_markup}</div>" if badge_markup else ""}</div>', unsafe_allow_html=True)

def render_hero() -> None:
    # Decorative illustration drawn locally; no external asset requests.
    nodes = '<path d="M95 44 200 105 300 48M95 44 55 160 200 105 270 205 300 48M55 160 160 225 270 205"/>'
    nodes += "".join(f'<circle cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in [(95,44,7),(300,48,6),(55,160,6),(160,225,5),(270,205,7)])
    st.markdown(f'<div class="hero"><div class="hero-content"><div class="hero-eyebrow">NETWORK INTELLIGENCE, SIMPLIFIED</div><h2>A clearer view.<br>A smarter defense.</h2><p>Turn network traffic into insight. Explore patterns, measure detection quality, and investigate individual connections.</p><div class="hero-tags"><span>UNSW-NB15</span><span>Validation-selected model</span></div></div><div class="hero-art"><svg viewBox="0 0 360 270" aria-hidden="true"><g fill="#183d49" stroke="#426874" stroke-width="1.2">{nodes}</g><circle cx="200" cy="105" r="62" fill="none" stroke="#32616a" stroke-dasharray="4 7"/><circle cx="200" cy="105" r="43" fill="#173e47" stroke="#57968e"/><g transform="translate(178,81) scale(2)" fill="none" stroke="#83d9bb" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">{ICON_PATHS["shield"]}</g></svg><span class="art-label">TRAFFIC → INSIGHT → ACTION</span></div></div>', unsafe_allow_html=True)

def render_metric_cards(cards: Sequence[dict]) -> None:
    markup = "".join(f'<div class="metric-card {escape(c.get("tone", "accent"))}"><div class="metric-top"><span>{escape(c.get("label", ""))}</span><span class="metric-icon">{icon(c.get("icon", "activity"), 18)}</span></div><div class="metric-value">{escape(c.get("value", "—"))}</div><div class="metric-sub">{escape(c.get("sub", ""))}</div></div>' for c in cards)
    st.markdown(f'<div class="metric-grid">{markup}</div>', unsafe_allow_html=True)

def render_section_header(title: str, copy: str = "", label: str = "") -> None:
    st.markdown(f'<div class="section-head"><div><h3>{escape(title)}</h3>{f"<p>{escape(copy)}</p>" if copy else ""}</div>{f"<span class=section-label>{escape(label)}</span>" if label else ""}</div>', unsafe_allow_html=True)

def render_callout(message: str, tone: str = "info") -> None:
    name = "check" if tone == "success" else "alert" if tone in ("warning", "danger") else "info"
    st.markdown(f'<div class="callout {escape(tone)}"><span>{icon(name, 18)}</span><div>{escape(message)}</div></div>', unsafe_allow_html=True)

def render_empty_state(title: str, copy: str, name: str = "activity") -> None:
    st.markdown(f'<div class="empty-state"><span class="empty-icon">{icon(name, 30)}</span><h3>{escape(title)}</h3><p>{escape(copy)}</p></div>', unsafe_allow_html=True)

def render_kv_panel(title: str, heading: str, rows: Sequence[tuple[str, object]]) -> None:
    markup = "".join(f'<div class="kv-line"><span>{escape(k)}</span><strong>{escape(v)}</strong></div>' for k, v in rows)
    st.markdown(f'<div class="panel"><div class="eyebrow">{escape(title)}</div><h3>{escape(heading)}</h3><div class="kv-list">{markup}</div></div>', unsafe_allow_html=True)

def render_tags(tags: Iterable[str]) -> None:
    st.markdown('<div class="tag-cloud">' + "".join(f'<span class="tag">{escape(t)}</span>' for t in tags) + '</div>', unsafe_allow_html=True)

def render_score_bars(scores: dict[str, float], colors: dict[str, str] | None = None) -> None:
    rows = []
    for name, value in scores.items():
        val = max(0.0, min(float(value or 0), 1.0))
        color = (colors or {}).get(name, ACCENT)
        rows.append(f'<div class="score-row"><span>{escape(name)}</span><div class="score-track"><div style="width:{val*100:.1f}%;background:{escape(color)}"></div></div><strong>{val:.3f}</strong></div>')
    st.markdown("".join(rows), unsafe_allow_html=True)

def render_footer() -> None:
    st.markdown('<div class="page-footer"><span>NetGuard · Network intelligence</span><span>UNSW-NB15 research workspace</span></div>', unsafe_allow_html=True)
