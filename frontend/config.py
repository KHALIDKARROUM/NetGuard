"""Public imports for the dashboard's shared design system and API client."""
from api import BACKEND_URL, api_get, api_post, explain_api_error
from theme import ACCENT, BORDER, DANGER, PAGE_CONFIG, PALETTE, PLOTLY_LAYOUT, SUCCESS, TEXT, TEXT_MUTED, VIOLET, WARNING
from ui import (
    escape, format_number, format_percent, format_rate, icon, panel, render_app_shell,
    render_callout, render_empty_state, render_footer, render_hero, render_kv_panel,
    render_metric_cards, render_page_header, render_score_bars, render_section_header,
    render_tags,
)
