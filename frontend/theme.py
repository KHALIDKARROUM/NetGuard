"""Color and chart tokens shared by every screen."""
ACCENT = "#0d8a7b"
SUCCESS = "#0d8a7b"
WARNING = "#b7791f"
DANGER = "#df6b61"
VIOLET = "#8a79c5"
TEXT = "#1b2b3b"
TEXT_MUTED = "#657589"
BORDER = "#e4e9ef"
PALETTE = [ACCENT, VIOLET, "#6899d0", DANGER, "#e2b56b", "#78b8a6"]
PAGE_CONFIG = dict(page_title="NetGuard · Network intelligence", page_icon="🛡️", layout="wide", initial_sidebar_state="auto")
PLOTLY_LAYOUT = dict(
    template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, sans-serif", color=TEXT_MUTED, size=12),
    margin=dict(l=20, r=20, t=24, b=30), colorway=PALETTE,
    xaxis=dict(gridcolor="#edf0f4", zerolinecolor=BORDER, linecolor=BORDER, tickfont=dict(size=11), automargin=True),
    yaxis=dict(gridcolor="#edf0f4", zerolinecolor=BORDER, linecolor=BORDER, tickfont=dict(size=11), automargin=True),
    legend=dict(orientation="h", yanchor="bottom", y=1.03, x=0, font=dict(size=11)),
    hoverlabel=dict(bgcolor="#ffffff", font=dict(color=TEXT, size=12)),
)
