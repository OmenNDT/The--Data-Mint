"""UI Theme & Design System for The Data Mint.

Custom Gradio theme + CSS cho dark mode professional AI/ML tool.
Brand color: Mint/Emerald — phù hợp tên "Data Mint".
"""

import gradio as gr

# =============================================================================
# COLOR TOKENS (Semantic)
# =============================================================================
COLORS = {
    # Background
    "bg_primary": "#0f172a",      # Slate 900 — main background
    "bg_secondary": "#1e293b",    # Slate 800 — cards/surfaces
    "bg_tertiary": "#334155",     # Slate 700 — elevated surfaces
    "bg_hover": "#475569",       # Slate 600 — hover states

    # Text
    "text_primary": "#f8fafc",    # Slate 50 — headings
    "text_secondary": "#cbd5e1",   # Slate 300 — body
    "text_muted": "#94a3b8",      # Slate 400 — labels/captions
    "text_disabled": "#64748b",    # Slate 500 — disabled

    # Accent (Mint/Emerald)
    "accent": "#10b981",          # Emerald 500
    "accent_hover": "#059669",    # Emerald 600
    "accent_light": "#34d399",    # Emerald 400 — gradients
    "accent_dim": "#065f46",      # Emerald 800 — subtle bg

    # Semantic
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "info": "#3b82f6",

    # Border
    "border": "#475569",
    "border_light": "#334155",
}

# =============================================================================
# TYPOGRAPHY
# =============================================================================
FONT_FAMILY = "Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"

# =============================================================================
# SPACING (8dp system)
# =============================================================================
SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "16px",
    "lg": "24px",
    "xl": "32px",
    "2xl": "48px",
}

# =============================================================================
# CUSTOM CSS
# =============================================================================
CUSTOM_CSS = """
/* ===== CSS VARIABLES ===== */
:root {
    --dm-bg-primary: #0f172a;
    --dm-bg-secondary: #1e293b;
    --dm-bg-tertiary: #334155;
    --dm-bg-hover: #475569;
    --dm-text-primary: #f8fafc;
    --dm-text-secondary: #cbd5e1;
    --dm-text-muted: #94a3b8;
    --dm-text-disabled: #64748b;
    --dm-accent: #10b981;
    --dm-accent-hover: #059669;
    --dm-accent-light: #34d399;
    --dm-accent-dim: #065f46;
    --dm-success: #22c55e;
    --dm-warning: #f59e0b;
    --dm-danger: #ef4444;
    --dm-info: #3b82f6;
    --dm-border: #475569;
    --dm-border-light: #334155;
    --dm-radius: 8px;
    --dm-radius-lg: 12px;
    --dm-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    --dm-shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
    --dm-shadow-glow: 0 0 12px rgba(16, 185, 129, 0.3);
}

/* ===== GLOBAL OVERRIDES ===== */
body {
    background: #0f172a !important;
    color: #cbd5e1 !important;
    font-family: Inter, system-ui, -apple-system, sans-serif !important;
}

/* Gradio container */
.gradio-container {
    background: #0f172a !important;
    color: #cbd5e1 !important;
}

/* ===== HEADER ===== */
.dm-header {
    text-align: center;
    margin-bottom: 24px;
    padding: 32px 24px;
    background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
    border-radius: 12px;
    border: 1px solid #475569;
    position: relative;
    overflow: hidden;
}
.dm-header::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #10b981, #34d399, #10b981);
}
.dm-header h1 {
    font-size: 1.875rem;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 8px;
    letter-spacing: -0.025em;
}
.dm-header p {
    font-size: 0.875rem;
    color: #94a3b8;
    margin: 0;
}
.dm-header .dm-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 12px;
    padding: 6px 14px;
    background: #065f46;
    border: 1px solid #10b981;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    color: #34d399;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ===== STATUS BAR ===== */
.dm-status-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    padding: 14px 18px;
    background: #1e293b;
    border-radius: 8px;
    border: 1px solid #475569;
    margin-bottom: 24px;
    align-items: center;
}
.dm-status-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.875rem;
    color: #cbd5e1;
}
.dm-status-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px #10b981;
    flex-shrink: 0;
}
.dm-status-indicator.offline {
    background: #ef4444;
    box-shadow: 0 0 8px #ef4444;
}
.dm-status-indicator.warning {
    background: #f59e0b;
    box-shadow: 0 0 8px #f59e0b;
}

/* ===== CARDS ===== */
.dm-card {
    background: #1e293b !important;
    border: 1px solid #475569 !important;
    border-radius: 12px !important;
    padding: 20px !important;
    margin-bottom: 16px !important;
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
.dm-card:hover {
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    border-color: #334155;
}
.dm-card-header {
    font-size: 1.125rem;
    font-weight: 600;
    color: #f8fafc;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.dm-card-header svg {
    color: #10b981;
    flex-shrink: 0;
}

/* ===== PHASE STEPPER ===== */
.dm-phase-stepper {
    display: flex;
    justify-content: space-between;
    margin-bottom: 24px;
    padding: 20px 16px;
    background: #1e293b;
    border-radius: 12px;
    border: 1px solid #475569;
    overflow-x: auto;
}
.dm-phase-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    flex: 1;
    position: relative;
    min-width: 60px;
}
.dm-phase-step:not(:last-child)::after {
    content: '';
    position: absolute;
    top: 14px;
    right: -50%;
    width: calc(100% - 20px);
    height: 2px;
    background: #334155;
    z-index: 0;
}
.dm-phase-step.active:not(:last-child)::after {
    background: linear-gradient(90deg, #10b981, #334155);
}
.dm-phase-step.completed:not(:last-child)::after {
    background: #10b981;
}
.dm-phase-step-number {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    background: #334155;
    color: #94a3b8;
    border: 2px solid #475569;
    z-index: 1;
    transition: all 0.2s ease;
}
.dm-phase-step.active .dm-phase-step-number {
    background: #10b981;
    color: white;
    border-color: #10b981;
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.3);
}
.dm-phase-step.completed .dm-phase-step-number {
    background: #10b981;
    color: white;
    border-color: #10b981;
}
.dm-phase-step-label {
    font-size: 0.7rem;
    color: #94a3b8;
    text-align: center;
    white-space: nowrap;
    font-weight: 500;
}
.dm-phase-step.active .dm-phase-step-label {
    color: #34d399;
}

/* ===== PROGRESS ===== */
.dm-progress-container {
    background: #1e293b;
    border: 1px solid #475569;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}
.dm-progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.dm-progress-phase {
    font-size: 0.875rem;
    font-weight: 600;
    color: #f8fafc;
}
.dm-progress-pct {
    font-size: 0.875rem;
    font-weight: 700;
    color: #10b981;
}
.dm-progress-bar-track {
    width: 100%;
    height: 8px;
    background: #334155;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 12px;
}
.dm-progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #10b981, #34d399);
    border-radius: 4px;
    transition: width 0.4s ease;
}
.dm-progress-stats {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #94a3b8;
}
.dm-progress-estimate {
    color: #34d399;
    font-weight: 500;
}

/* ===== EMPTY STATE ===== */
.dm-empty-state {
    text-align: center;
    padding: 48px 24px;
    color: #94a3b8;
}
.dm-empty-state-icon {
    margin-bottom: 16px;
    opacity: 0.4;
}
.dm-empty-state-icon svg {
    stroke: #94a3b8;
}
.dm-empty-state-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: #cbd5e1;
    margin-bottom: 8px;
}
.dm-empty-state-desc {
    font-size: 0.875rem;
    max-width: 400px;
    margin: 0 auto;
    line-height: 1.5;
}

/* ===== DEMO BANNER ===== */
.dm-demo-banner {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(245, 158, 11, 0.05));
    border: 1px solid rgba(245, 158, 11, 0.3);
    padding: 12px 16px;
    border-radius: 8px;
    text-align: center;
    font-weight: 600;
    color: #fbbf24;
    margin-bottom: 24px;
    font-size: 0.875rem;
}

/* ===== FORM HELPERS ===== */
.dm-helper-text {
    font-size: 0.75rem;
    color: #94a3b8;
    margin-top: 4px;
    line-height: 1.4;
}
.dm-input-group {
    margin-bottom: 16px;
}
.dm-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: #cbd5e1;
    margin-bottom: 6px;
    display: block;
}

/* ===== BUTTONS ===== */
.dm-btn-primary {
    background: linear-gradient(135deg, #10b981, #059669) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
.dm-btn-primary:hover {
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.3) !important;
    transform: translateY(-1px) !important;
}
.dm-btn-primary:active {
    transform: translateY(0) !important;
}
.dm-btn-primary:disabled {
    opacity: 0.5 !important;
    cursor: not-allowed !important;
    transform: none !important;
}

.dm-btn-secondary {
    background: #334155 !important;
    color: #cbd5e1 !important;
    border: 1px solid #475569 !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}
.dm-btn-secondary:hover {
    background: #475569 !important;
    border-color: #94a3b8 !important;
}

.dm-btn-danger {
    background: #ef4444 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    font-weight: 600 !important;
}

/* ===== METRIC CARDS ===== */
.dm-metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}
.dm-metric-card {
    background: #1e293b;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
    transition: border-color 0.2s ease;
}
.dm-metric-card:hover {
    border-color: #10b981;
}
.dm-metric-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 4px;
}
.dm-metric-label {
    font-size: 0.75rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.dm-metric-card.success .dm-metric-value { color: #22c55e; }
.dm-metric-card.warning .dm-metric-value { color: #f59e0b; }
.dm-metric-card.danger .dm-metric-value { color: #ef4444; }

/* ===== LOG DISPLAY ===== */
.dm-log-container {
    background: #0f172a;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 12px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.8rem;
    line-height: 1.6;
    color: #cbd5e1;
    max-height: 400px;
    overflow-y: auto;
}
.dm-log-line {
    padding: 2px 0;
    border-bottom: 1px solid rgba(71, 85, 105, 0.3);
}
.dm-log-line:last-child {
    border-bottom: none;
}
.dm-log-error { color: #fca5a5; }
.dm-log-warning { color: #fcd34d; }
.dm-log-success { color: #86efac; }
.dm-log-info { color: #93c5fd; }

/* ===== ANIMATIONS ===== */
@keyframes dm-pulse-glow {
    0%, 100% { box-shadow: 0 0 8px rgba(16, 185, 129, 0.3); }
    50% { box-shadow: 0 0 16px rgba(16, 185, 129, 0.5); }
}
.dm-running {
    animation: dm-pulse-glow 2s ease-in-out infinite;
}

@keyframes dm-fade-in {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
.dm-fade-in {
    animation: dm-fade-in 0.3s ease-out;
}

@keyframes dm-slide-in-right {
    from { opacity: 0; transform: translateX(12px); }
    to { opacity: 1; transform: translateX(0); }
}
.dm-slide-in {
    animation: dm-slide-in-right 0.25s ease-out;
}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #0f172a;
}
::-webkit-scrollbar-thumb {
    background: #334155;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #475569;
}

/* ===== TABS ===== */
.dm-tabs .tab-nav {
    background: #1e293b !important;
    border-bottom: 1px solid #475569 !important;
    border-radius: 12px 12px 0 0 !important;
}
.dm-tabs .tab-nav button {
    color: #94a3b8 !important;
    font-weight: 500 !important;
    padding: 12px 20px !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.2s ease !important;
}
.dm-tabs .tab-nav button:hover {
    color: #cbd5e1 !important;
    background: #334155 !important;
}
.dm-tabs .tab-nav button.selected {
    color: #10b981 !important;
    border-bottom: 2px solid #10b981 !important;
    background: transparent !important;
}
.dm-tabs .tab-content {
    background: #0f172a !important;
    border: 1px solid #475569 !important;
    border-top: none !important;
    border-radius: 0 0 12px 12px !important;
    padding: 20px !important;
}

/* ===== GALLERY ===== */
.dm-gallery {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 12px;
}
.dm-gallery-item {
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #475569;
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.dm-gallery-item:hover {
    transform: scale(1.02);
    border-color: #10b981;
}

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {
    .dm-phase-stepper {
        padding: 12px 8px;
    }
    .dm-phase-step-label {
        font-size: 0.6rem;
    }
    .dm-phase-step-number {
        width: 24px;
        height: 24px;
        font-size: 0.7rem;
    }
    .dm-header h1 {
        font-size: 1.5rem;
    }
    .dm-metric-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}
"""

# =============================================================================
# GRADIO THEME BUILDER
# =============================================================================
def create_theme() -> gr.themes.Base:
    """Create custom dark theme for The Data Mint.

    Returns:
        Gradio theme instance
    """
    return gr.themes.Soft(
        primary_hue="emerald",
        secondary_hue="slate",
        neutral_hue="slate",
        font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
    ).set(
        # Background
        body_background_fill="#0f172a",
        body_background_fill_dark="#0f172a",
        background_fill_primary="#1e293b",
        background_fill_primary_dark="#1e293b",
        background_fill_secondary="#334155",
        background_fill_secondary_dark="#334155",

        # Text
        body_text_color="#cbd5e1",
        body_text_color_dark="#f8fafc",
        body_text_color_subdued="#94a3b8",
        body_text_color_subdued_dark="#94a3b8",

        # Borders
        border_color_primary="#475569",
        border_color_primary_dark="#475569",
        border_color_accent="#10b981",
        border_color_accent_dark="#10b981",

        # Inputs
        input_background_fill="#1e293b",
        input_background_fill_dark="#1e293b",
        input_background_fill_focus="#1e293b",
        input_background_fill_focus_dark="#1e293b",
        input_border_color="#475569",
        input_border_color_dark="#475569",
        input_border_color_focus="#10b981",
        input_border_color_focus_dark="#10b981",
        input_placeholder_color="#64748b",
        input_placeholder_color_dark="#64748b",

        # Buttons - Primary
        button_primary_background_fill="#10b981",
        button_primary_background_fill_dark="#10b981",
        button_primary_background_fill_hover="#059669",
        button_primary_background_fill_hover_dark="#059669",
        button_primary_text_color="#ffffff",
        button_primary_text_color_dark="#ffffff",
        button_primary_text_color_hover="#ffffff",
        button_primary_text_color_hover_dark="#ffffff",
        button_primary_border_color="transparent",
        button_primary_border_color_dark="transparent",
        button_primary_border_color_hover="transparent",
        button_primary_border_color_hover_dark="transparent",

        # Buttons - Secondary
        button_secondary_background_fill="#334155",
        button_secondary_background_fill_dark="#334155",
        button_secondary_background_fill_hover="#475569",
        button_secondary_background_fill_hover_dark="#475569",
        button_secondary_text_color="#cbd5e1",
        button_secondary_text_color_dark="#cbd5e1",
        button_secondary_text_color_hover="#f8fafc",
        button_secondary_text_color_hover_dark="#f8fafc",
        button_secondary_border_color="#475569",
        button_secondary_border_color_dark="#475569",
        button_secondary_border_color_hover="#64748b",
        button_secondary_border_color_hover_dark="#64748b",

        # Buttons - Cancel (Stop)
        button_cancel_background_fill="#ef4444",
        button_cancel_background_fill_dark="#ef4444",
        button_cancel_background_fill_hover="#dc2626",
        button_cancel_background_fill_hover_dark="#dc2626",
        button_cancel_text_color="#ffffff",
        button_cancel_text_color_dark="#ffffff",

        # Radius (only settable properties)
        container_radius="12px",
        embed_radius="8px",
        input_radius="8px",
        button_large_radius="8px",
        button_medium_radius="8px",
        button_small_radius="6px",
        block_radius="12px",
        table_radius="8px",

        # Shadows
        shadow_drop="0 4px 6px -1px rgba(0, 0, 0, 0.3)",
        shadow_drop_lg="0 10px 15px -3px rgba(0, 0, 0, 0.4)",
        shadow_spread="0 0 12px rgba(16, 185, 129, 0.3)",
        shadow_spread_dark="0 0 12px rgba(16, 185, 129, 0.3)",
        block_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.3)",
        block_shadow_dark="0 4px 6px -1px rgba(0, 0, 0, 0.3)",

        # Block
        block_background_fill="#1e293b",
        block_background_fill_dark="#1e293b",
        block_border_color="#475569",
        block_border_color_dark="#475569",
        block_border_width="1px",
        block_border_width_dark="1px",
        block_label_background_fill="#334155",
        block_label_background_fill_dark="#334155",
        block_label_text_color="#f8fafc",
        block_label_text_color_dark="#f8fafc",
        block_label_text_weight="600",
        block_label_text_size="14px",
        block_title_text_color="#f8fafc",
        block_title_text_color_dark="#f8fafc",
        block_title_text_weight="600",
        block_title_text_size="16px",
        block_padding="20px",

        # Panel
        panel_background_fill="#1e293b",
        panel_background_fill_dark="#1e293b",
        panel_border_color="#475569",
        panel_border_color_dark="#475569",
        panel_border_width="1px",
        panel_border_width_dark="1px",

        # Table
        table_row_focus="#334155",
        table_row_focus_dark="#334155",
        table_odd_background_fill="#1e293b",
        table_odd_background_fill_dark="#1e293b",
        table_even_background_fill="#0f172a",
        table_even_background_fill_dark="#0f172a",
        table_border_color="#475569",
        table_border_color_dark="#475569",
        table_text_color="#cbd5e1",
        table_text_color_dark="#cbd5e1",

        # Slider
        slider_color="#10b981",
        slider_color_dark="#10b981",

        # Checkbox/Radio
        checkbox_background_color="#1e293b",
        checkbox_background_color_dark="#1e293b",
        checkbox_background_color_selected="#10b981",
        checkbox_background_color_selected_dark="#10b981",
        checkbox_border_color="#475569",
        checkbox_border_color_dark="#475569",
        checkbox_border_color_selected="#10b981",
        checkbox_border_color_selected_dark="#10b981",
        checkbox_label_text_color="#cbd5e1",
        checkbox_label_text_color_dark="#cbd5e1",
        checkbox_label_text_color_selected="#f8fafc",
        checkbox_label_text_color_selected_dark="#f8fafc",

        # Error states
        error_background_fill="#450a0a",
        error_background_fill_dark="#450a0a",
        error_border_color="#ef4444",
        error_border_color_dark="#ef4444",
        error_text_color="#fca5a5",
        error_text_color_dark="#fca5a5",
        error_icon_color="#ef4444",
        error_icon_color_dark="#ef4444",

        # Link
        link_text_color="#10b981",
        link_text_color_dark="#34d399",
        link_text_color_hover="#059669",
        link_text_color_hover_dark="#10b981",
        link_text_color_active="#059669",
        link_text_color_active_dark="#10b981",
        link_text_color_visited="#059669",
        link_text_color_visited_dark="#10b981",

        # Loader
        loader_color="#10b981",
        loader_color_dark="#10b981",

        # Code
        code_background_fill="#0f172a",
        code_background_fill_dark="#0f172a",

        # Accordion
        accordion_text_color="#f8fafc",
        accordion_text_color_dark="#f8fafc",

        # Stat
        stat_background_fill="#1e293b",
        stat_background_fill_dark="#1e293b",

        # Layout
        layout_gap="16px",
        form_gap_width="16px",

        # Section header
        section_header_text_size="16px",
        section_header_text_weight="600",

        # Prose
        prose_text_size="14px",
        prose_text_weight="400",
        prose_header_text_weight="600",
    )
