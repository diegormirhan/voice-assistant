"""The single source of truth for widget styling."""

from __future__ import annotations

from .theme import T, Palette


def build_qss(p: Palette) -> str:
    g0, g1 = p.accent_gradient
    return f"""
/* ── Base ─────────────────────────────────────────────────────── */
* {{
    font-family: "{T.font_ui}";
    font-size: 13px;
    outline: none;
}}
QWidget {{ color: {p.text}; }}
QMainWindow, QDialog {{ background: transparent; }}

/* ── Glass shells ─────────────────────────────────────────────── */
#glassCard {{
    background: {p.window};
    border: 1px solid {p.border};
    border-radius: {T.window_radius}px;
}}
#dialogCard {{
    background: {p.elevated};
    border: 1px solid {p.border};
    border-radius: {T.card_radius}px;
}}
#panel {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: {T.card_radius}px;
}}
#hairline {{ background: {p.border}; border: none; }}
#accentLine {{
    border: none;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {g0}, stop:0.45 {g1}, stop:1 transparent);
}}

/* ── Typography ───────────────────────────────────────────────── */
QLabel {{ background: transparent; border: none; }}
QLabel[role="title"] {{
    font-family: "{T.font_display}";
    font-size: 19px;
    font-weight: 600;
    color: {p.text};
}}
QLabel[role="section"] {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.4px;
    color: {p.text_faint};
}}
QLabel[role="label"] {{ font-size: 13px; color: {p.text}; }}
QLabel[role="value"] {{
    font-family: "{T.font_mono}";
    font-size: 12px;
    color: {p.text_dim};
}}
QLabel[role="hint"] {{ font-size: 11px; color: {p.text_faint}; }}
QLabel[role="status"] {{
    font-size: 12px;
    letter-spacing: 0.6px;
    color: {p.text_dim};
}}

/* ── Buttons ──────────────────────────────────────────────────── */
QPushButton {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: {T.pill_radius}px;
    padding: 8px 16px;
    color: {p.text};
}}
QPushButton:hover {{
    background: {p.surface_hover};
    border-color: {p.border_strong};
}}
QPushButton:pressed {{ background: {p.surface_active}; }}
QPushButton:disabled {{ color: {p.text_faint}; border-color: {p.border}; }}

QPushButton[variant="primary"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {g0}, stop:1 {g1});
    border: 1px solid transparent;
    color: {p.on_accent};
    font-weight: 600;
    padding: 9px 24px;
}}
QPushButton[variant="primary"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {g1}, stop:1 {g0});
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid {p.border};
    color: {p.text_dim};
}}
QPushButton[variant="ghost"]:hover {{
    background: {p.surface};
    color: {p.text};
    border-color: {p.border_strong};
}}
QPushButton[variant="quiet"] {{
    background: transparent;
    border: none;
    color: {p.text_dim};
    padding: 5px 6px;
    text-align: left;
}}
QPushButton[variant="quiet"]:hover {{ color: {p.accent}; }}

#iconBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {T.control_radius}px;
    padding: 0;
}}
#iconBtn:hover {{
    background: {p.surface_hover};
    border-color: {p.border};
}}
#iconBtn:pressed {{ background: {p.surface_active}; }}
#iconBtn:checked {{
    background: {p.accent_soft};
    border-color: {p.accent};
}}
#closeBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {T.control_radius}px;
    padding: 0;
}}
#closeBtn:hover {{ background: {p.danger}; border-color: {p.danger}; }}
#powerBtn {{ background: transparent; border: none; padding: 0; }}

/* ── Combo boxes ──────────────────────────────────────────────── */
QComboBox {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: {T.pill_radius}px;
    /* The leading item icon is drawn by Qt at the content edge, so the text
       needs its own left inset or the two collide. */
    padding: 6px 12px;
    padding-left: 34px;
    padding-right: 30px;
    min-width: 104px;
    color: {p.text};
}}
QComboBox:hover {{ background: {p.surface_hover}; border-color: {p.border_strong}; }}
QComboBox:focus {{ border-color: {p.accent}; }}
QComboBox:on {{ background: {p.surface_active}; border-color: {p.accent}; }}
QComboBox:disabled {{ color: {p.text_dim}; border-color: {p.border}; }}
QComboBox::drop-down {{
    /* The chevron is painted by PillSelect; keep the native slot invisible. */
    width: 0;
    border: none;
}}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background: {p.elevated};
    border: 1px solid {p.border_strong};
    border-radius: {T.control_radius}px;
    padding: 6px;
    color: {p.text};
    outline: none;
    selection-background-color: {p.accent_soft};
    selection-color: {p.text};
}}
QComboBox QAbstractItemView::item {{
    padding: 7px 10px;
    border-radius: 8px;
    min-height: 24px;
}}
QComboBox QAbstractItemView::item:hover {{ background: {p.surface_hover}; }}
QComboBox QAbstractItemView::item:selected {{ background: {p.accent_soft}; }}

/* ── Info explainer blocks ────────────────────────────────────── */
#infoBlock {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: {T.control_radius}px;
}}
#infoItem {{
    color: {p.text_dim};
    background: {p.surface_hover};
    border-radius: 8px;
    padding: 6px 9px;
}}


/* ── Sliders ──────────────────────────────────────────────────── */
QSlider {{ min-height: 22px; }}
QSlider::groove:horizontal {{
    height: 4px;
    background: {p.surface_active};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    height: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {g0}, stop:1 {g1});
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {p.text};
    border: none;
    width: 13px; height: 13px;
    border-radius: 6px;
    margin: -5px 0;
}}
QSlider::handle:horizontal:hover {{ background: {p.accent_hover}; }}
QSlider::handle:horizontal:disabled {{ background: {p.text_faint}; }}

/* ── Scroll areas ─────────────────────────────────────────────── */
QScrollArea, #transcriptScroll {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {p.surface_active};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.border_strong}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0; }}

/* ── Transcript bubbles ───────────────────────────────────────── */
#bubbleUser {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {g0}, stop:1 {g1});
    border: none;
    border-radius: {T.bubble_radius}px;
    color: {p.on_accent};
    padding: 9px 13px;
}}
#bubbleAssistant {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: {T.bubble_radius}px;
    color: {p.text};
    padding: 9px 13px;
}}
#bubbleMeta {{ color: {p.text_faint}; font-size: 10px; }}
#bubbleMetaOnAccent {{ color: {p.on_accent}; font-size: 10px; }}

/* ── Tooltip ──────────────────────────────────────────────────── */
QToolTip {{
    background: {p.elevated};
    color: {p.text};
    border: 1px solid {p.border};
    border-radius: {T.control_radius}px;
    padding: 7px 10px;
}}
"""
