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
        "hint": "Comparer les modeles et leurs courbes",
    },
    {
        "key": "prediction",
        "label": "Prediction",
        "path": "pages/03_prediction.py",
        "icon": ":material/radar:",
        "hint": "Lancer une inference en temps reel",
    },
)

# Shared colors and chart theme
PALETTE = [
    "#38bdf8",
    "#5eead4",
    "#22c55e",
    "#f59e0b",
    "#fb7185",
    "#f97316",
]
ACCENT = "#38bdf8"
SUCCESS = "#22c55e"
WARNING = "#f59e0b"
DANGER = "#fb7185"
TEXT_MUTED = "#93a7c0"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Space Grotesk, sans-serif", color="#dce8f7", size=12),
    margin=dict(l=40, r=20, t=45, b=40),
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
    legend=dict(font=dict(color="#dce8f7")),
)

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
    --bg-0: #030d18;
    --bg-1: #081523;
    --bg-2: #10263b;
    --surface: rgba(8, 21, 36, 0.78);
    --surface-strong: rgba(10, 24, 39, 0.94);
    --surface-soft: rgba(12, 28, 45, 0.58);
    --border: rgba(148, 163, 184, 0.16);
    --border-strong: rgba(94, 234, 212, 0.30);
    --text: #f2f7ff;
    --muted: #96abc5;
    --accent: #48c7f9;
    --accent-soft: rgba(72, 199, 249, 0.16);
    --accent-2: #64f0cf;
    --success: #22c55e;
    --warning: #f59e0b;
    --danger: #fb7185;
    --shadow: 0 24px 70px rgba(2, 8, 23, 0.45);
    --shadow-soft: 0 18px 42px rgba(2, 8, 23, 0.28);
}

html {
    scroll-behavior: smooth;
}

html, body, [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 12% 10%, rgba(72, 199, 249, 0.18), transparent 22%),
        radial-gradient(circle at 86% 12%, rgba(100, 240, 207, 0.11), transparent 24%),
        radial-gradient(circle at 50% 0%, rgba(247, 178, 103, 0.08), transparent 22%),
        linear-gradient(180deg, var(--bg-0) 0%, var(--bg-1) 52%, #071422 100%);
    color: var(--text);
    font-family: 'Space Grotesk', sans-serif;
}

[data-testid="stAppViewContainer"]::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(148, 163, 184, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(148, 163, 184, 0.04) 1px, transparent 1px);
    background-size: 32px 32px;
    mask-image: linear-gradient(180deg, rgba(255,255,255,0.22), transparent 82%);
    pointer-events: none;
}

[data-testid="stAppViewContainer"] > .main {
    padding: 0 !important;
}

section.main > div {
    max-width: 1380px;
    padding-top: 0 !important;
}

.block-container {
    max-width: 1380px;
    padding: 1.1rem 1.5rem 3.2rem;
}

#MainMenu, header, footer, [data-testid="stSidebar"], [data-testid="stSidebarNav"] {
    display: none !important;
}

[data-testid="stDecoration"] {
    display: none !important;
}

h1, h2, h3, h4 {
    font-family: 'Space Grotesk', sans-serif;
    color: var(--text);
    letter-spacing: -0.03em;
}

p, li, label, .stMarkdown, .stText {
    color: var(--muted);
}

code {
    font-family: 'IBM Plex Mono', monospace !important;
    color: #cfe7ff !important;
}

.shell-meta {
    margin-bottom: 0.55rem;
    color: var(--accent-2);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}

.shell-panel {
    height: 100%;
    padding: 1rem 1.1rem;
    border-radius: 24px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background:
        linear-gradient(180deg, rgba(10, 22, 36, 0.92), rgba(7, 17, 29, 0.82));
    backdrop-filter: blur(18px);
    box-shadow: var(--shadow-soft);
    position: relative;
    overflow: hidden;
}

.shell-panel::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 1px;
    background: linear-gradient(90deg, rgba(255,255,255,0.14), transparent 62%);
}

.brand-lockup {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    min-height: 52px;
}

.brand-mark {
    width: 52px;
    height: 52px;
    border-radius: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background:
        radial-gradient(circle at 28% 20%, rgba(255,255,255,0.34), transparent 32%),
        linear-gradient(135deg, var(--accent), var(--accent-2));
    color: #04101c;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.84rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    box-shadow: 0 16px 30px rgba(56, 189, 248, 0.28);
}

.brand-copy {
    display: flex;
    flex-direction: column;
    gap: 0.18rem;
}

.brand-name {
    color: var(--text);
    font-size: 1.04rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}

.brand-meta {
    color: var(--muted);
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
}

.brand-badge {
    display: inline-flex;
    align-items: center;
    margin-top: 0.9rem;
    padding: 0.36rem 0.72rem;
    border-radius: 999px;
    border: 1px solid rgba(94, 234, 212, 0.16);
    background: rgba(12, 29, 45, 0.68);
    color: #dce8f7;
    font-size: 0.74rem;
    font-family: 'IBM Plex Mono', monospace;
}

.nav-helper {
    margin: 0.1rem 0 0.9rem;
    color: #c7d6e6;
    font-size: 0.82rem;
    line-height: 1.65;
}

div[data-testid="stPageLink"] {
    width: 100%;
}

a[data-testid="stPageLink-NavLink"] {
    width: 100% !important;
    min-height: 64px;
    border-radius: 18px !important;
    border: 1px solid rgba(148, 163, 184, 0.14) !important;
    background:
        linear-gradient(180deg, rgba(11, 24, 39, 0.92), rgba(8, 18, 29, 0.82)) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.04),
        0 14px 30px rgba(2, 8, 23, 0.18);
    padding: 0.9rem 1rem !important;
    transition:
        transform 0.18s ease,
        border-color 0.18s ease,
        background 0.18s ease,
        box-shadow 0.18s ease !important;
}

a[data-testid="stPageLink-NavLink"] [data-testid="stMarkdownContainer"] p {
    margin: 0;
    color: #d4e2f1;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.88rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}

a[data-testid="stPageLink-NavLink"]:hover {
    transform: translateY(-2px);
    border-color: rgba(72, 199, 249, 0.28) !important;
    background:
        linear-gradient(180deg, rgba(12, 27, 44, 0.96), rgba(9, 21, 35, 0.88)) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.05),
        0 18px 34px rgba(2, 8, 23, 0.24);
}

a[data-testid="stPageLink-NavLink"]:has(strong) {
    transform: translateY(-1px);
    border-color: rgba(100, 240, 207, 0.34) !important;
    background:
        linear-gradient(135deg, rgba(72, 199, 249, 0.20), rgba(100, 240, 207, 0.15)) !important;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.08),
        0 18px 40px rgba(56, 189, 248, 0.18);
}

a[data-testid="stPageLink-NavLink"]:has(strong) [data-testid="stMarkdownContainer"] p {
    color: var(--text);
}

a[data-testid="stPageLink-NavLink"] svg {
    color: var(--accent-2);
}

.status-chip {
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
    gap: 0.55rem;
    min-height: 52px;
    width: 100%;
    padding: 0.75rem 0.95rem;
    border-radius: 18px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: rgba(8, 20, 33, 0.72);
    color: var(--text);
    font-size: 0.82rem;
    font-weight: 600;
}

.status-chip-dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    flex-shrink: 0;
}

.status-chip.ok .status-chip-dot {
    background: var(--success);
    box-shadow: 0 0 0 8px rgba(34, 197, 94, 0.14);
}

.status-chip.warn .status-chip-dot {
    background: var(--warning);
    box-shadow: 0 0 0 8px rgba(245, 158, 11, 0.14);
}

.status-copy {
    margin: 0.75rem 0 0;
    color: #bbcbdd;
    font-size: 0.8rem;
    line-height: 1.65;
}

.shell-divider {
    margin: 1.15rem 0 1.6rem;
    height: 1px;
    border: none;
    background: linear-gradient(90deg, rgba(100, 240, 207, 0.26), rgba(148, 163, 184, 0.10), transparent 78%);
}

.hero-panel {
    position: relative;
    overflow: hidden;
    padding: 2.35rem;
    border-radius: 30px;
    background:
        radial-gradient(circle at 82% 10%, rgba(100, 240, 207, 0.18), transparent 30%),
        radial-gradient(circle at 12% 18%, rgba(72, 199, 249, 0.12), transparent 24%),
        linear-gradient(135deg, rgba(11, 27, 44, 0.98), rgba(7, 17, 29, 0.92));
    border: 1px solid var(--border-strong);
    box-shadow: var(--shadow);
    margin-bottom: 1.5rem;
}

.hero-panel::before {
    content: "";
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px);
    background-size: 32px 32px;
    mask-image: linear-gradient(135deg, rgba(255,255,255,0.34), transparent 70%);
    pointer-events: none;
}

.hero-panel::after {
    content: "";
    position: absolute;
    right: -8%;
    top: -25%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.22) 0%, transparent 72%);
    pointer-events: none;
}

.hero-grid {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(240px, 0.85fr);
    gap: 1.4rem;
    align-items: end;
}

.hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    margin-bottom: 1rem;
    color: var(--accent-2);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}

.hero-title {
    margin: 0 0 0.9rem;
    font-size: clamp(2rem, 4vw, 3.6rem);
    line-height: 0.98;
    color: var(--text);
}

.hero-copy {
    margin: 0;
    max-width: 720px;
    color: #c1d0df;
    font-size: 1rem;
    line-height: 1.85;
}

.hero-summary {
    padding: 1.15rem 1.2rem;
    border-radius: 24px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: rgba(7, 20, 33, 0.68);
    backdrop-filter: blur(14px);
    box-shadow: 0 14px 34px rgba(2, 8, 23, 0.18);
}

.hero-summary-label {
    color: var(--accent-2);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.9rem;
}

.hero-summary-list {
    display: grid;
    gap: 0.75rem;
}

.hero-summary-item {
    display: grid;
    grid-template-columns: 34px 1fr;
    gap: 0.8rem;
    align-items: start;
}

.hero-summary-index {
    width: 34px;
    height: 34px;
    border-radius: 12px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, rgba(72, 199, 249, 0.18), rgba(100, 240, 207, 0.18));
    color: var(--text);
    font-size: 0.76rem;
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
}

.hero-summary-text {
    color: #d4e2f1;
    font-size: 0.84rem;
    line-height: 1.65;
}

.chip-row {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 1.55rem;
    position: relative;
    z-index: 1;
}

.chip {
    display: inline-flex;
    align-items: center;
    padding: 0.48rem 0.82rem;
    border-radius: 999px;
    background: rgba(12, 28, 45, 0.62);
    border: 1px solid rgba(72, 199, 249, 0.14);
    color: var(--text);
    font-size: 0.76rem;
    font-weight: 500;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}

.metric-card,
.panel,
.quick-card,
.ranking-row,
.result-banner {
    position: relative;
    overflow: hidden;
    transition:
        transform 0.2s ease,
        border-color 0.2s ease,
        box-shadow 0.2s ease;
}

.metric-card::before,
.panel::before,
.quick-card::before,
.result-banner::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 1px;
    background: linear-gradient(90deg, rgba(255,255,255,0.14), transparent 68%);
}

.metric-card:hover,
.panel:hover,
.quick-card:hover,
.ranking-row:hover {
    transform: translateY(-3px);
    border-color: rgba(100, 240, 207, 0.22);
    box-shadow: 0 22px 44px rgba(2, 8, 23, 0.26);
}

.metric-card {
    height: 100%;
    padding: 1.25rem 1.3rem;
    border-radius: 22px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: linear-gradient(180deg, rgba(11, 26, 42, 0.84), rgba(8, 18, 30, 0.76));
    backdrop-filter: blur(12px);
    box-shadow: var(--shadow-soft);
}

.metric-card.accent {
    border-color: rgba(56, 189, 248, 0.28);
}

.metric-card.success {
    border-color: rgba(34, 197, 94, 0.24);
}

.metric-card.danger {
    border-color: rgba(251, 113, 133, 0.24);
}

.metric-label {
    color: var(--muted);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 0.5rem;
}

.metric-value {
    color: var(--text);
    font-size: 1.85rem;
    line-height: 1;
    font-weight: 700;
    letter-spacing: -0.03em;
}

.metric-value.accent {
    color: var(--accent);
}

.metric-value.success {
    color: var(--success);
}

.metric-value.warning {
    color: var(--warning);
}

.metric-value.danger {
    color: var(--danger);
}

.metric-sub {
    margin-top: 0.45rem;
    color: var(--muted);
    font-size: 0.8rem;
}

.panel {
    height: 100%;
    padding: 1.35rem 1.45rem;
    border-radius: 24px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: linear-gradient(180deg, rgba(10, 23, 38, 0.84), rgba(8, 18, 29, 0.76));
    backdrop-filter: blur(12px);
    box-shadow: var(--shadow-soft);
}

.panel-title {
    color: var(--accent-2);
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 0.95rem;
}

.panel-heading {
    color: var(--text);
    font-size: 1.08rem;
    font-weight: 700;
    margin-bottom: 0.75rem;
    letter-spacing: -0.02em;
}

.panel-copy {
    color: #b7c7da;
    font-size: 0.92rem;
    line-height: 1.8;
    margin: 0;
}

.section-heading {
    margin: 1.75rem 0 1rem;
    color: var(--text);
    font-size: 1.14rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}

.section-kicker {
    margin-bottom: 0.3rem;
    color: var(--accent-2);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}

.callout {
    padding: 1rem 1.1rem;
    border-radius: 20px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: rgba(11, 24, 39, 0.72);
    color: #cbd8e8;
    font-size: 0.9rem;
    line-height: 1.75;
    margin: 1rem 0;
    box-shadow: 0 14px 30px rgba(2, 8, 23, 0.14);
}

.callout.info {
    border-left: 3px solid var(--accent);
}

.callout.warn {
    border-left: 3px solid var(--warning);
}

.callout.danger {
    border-left: 3px solid var(--danger);
}

.stat-list {
    display: grid;
    gap: 0.7rem;
}

.stat-line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid rgba(148, 163, 184, 0.10);
}

.stat-line:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.stat-key {
    color: var(--muted);
    font-size: 0.85rem;
}

.stat-value {
    color: var(--text);
    font-size: 0.85rem;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    text-align: right;
}

.tag-cloud {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
}

.tag-pill {
    display: inline-flex;
    align-items: center;
    padding: 0.38rem 0.74rem;
    border-radius: 999px;
    background: rgba(72, 199, 249, 0.10);
    border: 1px solid rgba(72, 199, 249, 0.18);
    color: var(--text);
    font-size: 0.76rem;
    font-family: 'IBM Plex Mono', monospace;
}

.ranking-row {
    display: grid;
    grid-template-columns: 48px 1fr 92px;
    gap: 1rem;
    align-items: center;
    padding: 1rem 1.1rem;
    border-radius: 22px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: linear-gradient(180deg, rgba(10, 22, 35, 0.74), rgba(8, 18, 29, 0.68));
    margin-bottom: 0.7rem;
}

.ranking-row.active {
    border-color: rgba(100, 240, 207, 0.30);
    background: linear-gradient(180deg, rgba(10, 32, 44, 0.92), rgba(8, 22, 33, 0.86));
}

.ranking-rank {
    width: 48px;
    height: 48px;
    border-radius: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(56, 189, 248, 0.10);
    color: var(--text);
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
}

.ranking-name {
    color: var(--text);
    font-size: 0.98rem;
    font-weight: 700;
}

.ranking-meta {
    margin-top: 0.22rem;
    color: var(--muted);
    font-size: 0.8rem;
    line-height: 1.7;
}

.ranking-track,
.score-track {
    margin-top: 0.75rem;
    width: 100%;
    height: 8px;
    border-radius: 999px;
    background: rgba(148, 163, 184, 0.14);
    overflow: hidden;
}

.ranking-fill,
.score-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--accent), var(--accent-2));
}

.ranking-score {
    color: var(--text);
    font-size: 1rem;
    font-weight: 700;
    text-align: right;
    font-family: 'IBM Plex Mono', monospace;
}

.quick-card {
    height: 100%;
    padding: 1.35rem 1.45rem;
    border-radius: 24px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: linear-gradient(180deg, rgba(10, 23, 38, 0.88), rgba(7, 17, 29, 0.78));
    box-shadow: var(--shadow-soft);
}

.quick-card-title {
    color: var(--text);
    font-size: 1.02rem;
    font-weight: 700;
    margin-bottom: 0.55rem;
}

.quick-card-copy {
    color: #b7c7da;
    font-size: 0.9rem;
    line-height: 1.75;
    margin-bottom: 0.95rem;
}

.result-banner {
    padding: 1.4rem 1.5rem;
    border-radius: 24px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: linear-gradient(180deg, rgba(10, 23, 38, 0.88), rgba(8, 18, 29, 0.80));
}

.result-banner.success {
    border-color: rgba(34, 197, 94, 0.28);
    background: rgba(7, 30, 21, 0.84);
}

.result-banner.danger {
    border-color: rgba(251, 113, 133, 0.28);
    background: rgba(39, 10, 18, 0.84);
}

.result-tag {
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}

.result-title {
    color: var(--text);
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.05;
    margin: 0.45rem 0 0.35rem;
}

.result-copy {
    color: #d4e1ef;
    font-size: 0.92rem;
    line-height: 1.75;
}

.score-row {
    display: grid;
    grid-template-columns: 150px 64px 1fr 70px;
    gap: 0.8rem;
    align-items: center;
    padding: 0.7rem 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.10);
}

.score-row:last-child {
    border-bottom: none;
}

.score-name {
    color: var(--text);
    font-size: 0.85rem;
    font-weight: 600;
}

.score-weight {
    color: var(--muted);
    font-size: 0.76rem;
    font-family: 'IBM Plex Mono', monospace;
}

.score-value {
    color: var(--text);
    font-size: 0.82rem;
    font-family: 'IBM Plex Mono', monospace;
    text-align: right;
}

.helper-note {
    margin-top: 0.35rem;
    padding: 0.82rem 0.92rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.12);
    background: rgba(12, 28, 45, 0.52);
    color: var(--muted);
    font-size: 0.78rem;
    line-height: 1.7;
}

div[data-testid="stForm"] {
    padding: 1rem 1.05rem 0.55rem;
    border-radius: 26px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: linear-gradient(180deg, rgba(10, 23, 38, 0.82), rgba(7, 17, 29, 0.76));
    box-shadow: var(--shadow-soft);
}

[data-testid="stRadio"] [role="radiogroup"] {
    display: flex;
    gap: 0.7rem;
    padding: 0.22rem;
    border-radius: 18px;
    background: rgba(8, 20, 33, 0.52);
}

[data-testid="stRadio"] [role="radiogroup"] label {
    min-height: 48px;
    padding: 0.5rem 0.9rem;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.14);
    background: rgba(11, 24, 39, 0.86);
}

[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
    border-color: rgba(100, 240, 207, 0.30);
    background: linear-gradient(135deg, rgba(72, 199, 249, 0.18), rgba(100, 240, 207, 0.16));
}

[data-testid="stRadio"] [role="radiogroup"] p {
    color: #d7e4f1;
    font-size: 0.84rem;
    font-weight: 600;
}

div[data-testid="stButton"],
div[data-testid="stFormSubmitButton"] {
    margin-top: 0.55rem;
}

div[data-testid="stButton"] > button,
div[data-testid="stFormSubmitButton"] > button {
    min-height: 48px;
    border-radius: 999px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-size: 0.86rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em;
    border: 1px solid rgba(72, 199, 249, 0.18) !important;
    color: var(--text) !important;
    background: linear-gradient(180deg, rgba(10, 22, 35, 0.84), rgba(8, 18, 29, 0.72)) !important;
    transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), 0 14px 26px rgba(2, 8, 23, 0.16) !important;
}

div[data-testid="stButton"] > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px);
    border-color: rgba(100, 240, 207, 0.34) !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 18px 30px rgba(2, 8, 23, 0.22) !important;
    color: var(--text) !important;
}

div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stFormSubmitButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent), var(--accent-2)) !important;
    color: #04101c !important;
    border: none !important;
    box-shadow: 0 16px 28px rgba(56, 189, 248, 0.24) !important;
}

div[data-testid="stButton"] > button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
    color: #04101c !important;
}

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0.55rem;
    margin-bottom: 0.35rem;
}

[data-testid="stTabs"] [data-baseweb="tab"] {
    background: rgba(10, 22, 35, 0.74);
    border: 1px solid rgba(148, 163, 184, 0.14);
    border-radius: 999px;
    padding: 0.56rem 1.02rem;
    color: var(--muted);
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.84rem;
    font-weight: 600;
}

[data-testid="stTabs"] [aria-selected="true"] {
    color: var(--text) !important;
    border-color: rgba(100, 240, 207, 0.32) !important;
    background: linear-gradient(135deg, rgba(72, 199, 249, 0.16), rgba(100, 240, 207, 0.14)) !important;
}

[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    display: none;
}

[data-testid="stDataFrame"] {
    border: 1px solid rgba(148, 163, 184, 0.14) !important;
    border-radius: 22px;
    overflow: hidden;
    background: rgba(8, 20, 33, 0.58) !important;
    box-shadow: var(--shadow-soft);
}

[data-testid="stDataFrame"] * {
    font-family: 'IBM Plex Mono', monospace !important;
}

[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"] {
    border-radius: 16px !important;
    border-color: rgba(148, 163, 184, 0.16) !important;
    background: rgba(10, 22, 35, 0.76) !important;
    color: var(--text) !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

[data-testid="stNumberInput"] input:focus,
[data-testid="stTextInput"] input:focus,
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="base-input"]:focus-within {
    border-color: rgba(94, 234, 212, 0.28) !important;
    box-shadow: 0 0 0 1px rgba(94, 234, 212, 0.28) !important;
}

label[data-testid="stWidgetLabel"] {
    color: var(--muted) !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}

[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    border-color: var(--accent) !important;
    background: var(--accent) !important;
}

[data-testid="stSlider"] [data-baseweb="slider"] > div:first-child {
    background: rgba(148, 163, 184, 0.16) !important;
}

.js-plotly-plot .plotly,
.js-plotly-plot .plotly svg {
    background: transparent !important;
}

@media (max-width: 980px) {
    .block-container {
        padding: 1rem 1rem 2rem;
    }

    .shell-panel {
        padding: 0.95rem 1rem;
    }

    .hero-panel {
        padding: 1.55rem;
    }

    .hero-grid {
        grid-template-columns: 1fr;
    }

    .hero-title {
        font-size: 2rem;
    }

    .score-row {
        grid-template-columns: 1fr;
        gap: 0.35rem;
    }

    .ranking-row {
        grid-template-columns: 1fr;
    }

    [data-testid="stRadio"] [role="radiogroup"] {
        flex-direction: column;
    }
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
            "`python main.py` depuis le dossier `backend`, puis recharge la page. "
            "Si le backend tourne sur une autre adresse, definis `BACKEND_URL` "
            "avant de lancer Streamlit."
        )

    if isinstance(exc, requests.Timeout):
        return (
            f"Le backend sur {BACKEND_URL} ne repond pas avant le delai imparti. "
            "Verifie que l'API est bien demarree et qu'elle n'est pas bloquee au chargement."
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
            "Toutes les visualisations et les predictions sont synchronisees avec le backend."
            if is_online
            else "Le shell reste navigable, mais les vues dependantes de l'API pourront afficher une erreur."
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
    badge_values = [str(badge) for badge in (badges or []) if str(badge).strip()]
    badge_markup = "".join(
        f'<span class="chip">{html.escape(badge)}</span>'
        for badge in badge_values
    )

    summary_items_markup = "".join(
        (
            '<div class="hero-summary-item">'
            f'<span class="hero-summary-index">{index:02d}</span>'
            f'<div class="hero-summary-text">{html.escape(badge)}</div>'
            "</div>"
        )
        for index, badge in enumerate(badge_values[:3], start=1)
    )

    summary_markup = ""
    if summary_items_markup:
        summary_markup = (
            '<aside class="hero-summary">'
            '<div class="hero-summary-label">Contexte direct</div>'
            f'<div class="hero-summary-list">{summary_items_markup}</div>'
            "</aside>"
        )

    header_markup = (
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
        "</section>"
    )

    st.markdown(header_markup, unsafe_allow_html=True)


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
