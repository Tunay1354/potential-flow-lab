"""
theme.py — ALL visual decisions live here.

To revise the look of the program, change values in this file only:
  * LIGHT / DARK  -> colors
  * FONT          -> font family and size
  * LAYOUT        -> sizes of panels, icons, window, etc.
Nothing else in the code contains hard-coded colors or sizes.
"""

# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------
LIGHT = {
    "name": "light",
    # General UI
    "window_bg":   "#F3F5F8",
    "panel_bg":    "#FFFFFF",
    "panel_header": "#EEF2F7",
    "border":      "#D8DEE6",
    "text":        "#1E2633",
    "text_muted":  "#6B7685",
    "accent":      "#1F4E8C",   # main brand color (navy blue)
    "accent_hover": "#2A63AE",
    "accent_soft": "#E2EBF7",   # selected / hover backgrounds
    "accent_text": "#FFFFFF",
    "danger":      "#C0392B",
    # Plot
    "plot_bg":     "#FFFFFF",
    "plot_grid":   "#E7EBF0",
    "plot_axis":   "#4A5568",
    "streamline":  "#1F6FB2",
    "dividing_streamline": "#0F2A47",
    "body_fill":   "#DCE3EC",
    "body_edge":   "#334155",
    # Element colors (used for toolbar icons, list icons and plot markers)
    "el_uniform":  "#2F80ED",
    "el_source":   "#E5533D",
    "el_sink":     "#2D9CDB",
    "el_vortex":   "#8E44AD",
    "el_doublet":  "#E67E22",
    "el_sector":   "#27AE60",
    "el_wall":     "#4F5B66",
}

DARK = {
    "name": "dark",
    "window_bg":   "#1B1F26",
    "panel_bg":    "#232833",
    "panel_header": "#2A303C",
    "border":      "#363D4A",
    "text":        "#E6EAF0",
    "text_muted":  "#9AA4B2",
    "accent":      "#5B9BE6",
    "accent_hover": "#78AEEE",
    "accent_soft": "#2B3B53",
    "accent_text": "#0F141B",
    "danger":      "#E57368",
    "plot_bg":     "#14171C",
    "plot_grid":   "#262B33",
    "plot_axis":   "#AAB3C0",
    "streamline":  "#6FB6FF",
    "dividing_streamline": "#FFFFFF",
    "body_fill":   "#2E3644",
    "body_edge":   "#C9D2DE",
    "el_uniform":  "#5DA0F5",
    "el_source":   "#FF7A66",
    "el_sink":     "#56B9F0",
    "el_vortex":   "#B57BD6",
    "el_doublet":  "#F5A25D",
    "el_sector":   "#4CCB7E",
    "el_wall":     "#A7B1BC",
}

DEFAULT_THEME = LIGHT

# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
FONT = {
    # First available family is used (Windows -> Segoe UI, macOS -> SF / Helvetica)
    "families": ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Arial"],
    "size_pt": 10,
    "plot_label_size_pt": 11,
}

# ---------------------------------------------------------------------------
# Layout / sizes
# ---------------------------------------------------------------------------
LAYOUT = {
    "window_title": "Potential Flow Lab",
    "window_size": (1400, 860),
    "toolbar_icon_px": 34,
    "toolbar_show_text": False,     # True -> element names under toolbar icons
    "right_panel_width": 330,
    "elements_panel_min_height": 210,
    "plot_initial_range": {"x": (-4.0, 4.0), "y": (-2.6, 2.6)},
    "streamline_width": 1.4,
    "dividing_streamline_width": 2.4,
    "arrow_size_px": 6.5,           # width of the streamline arrow heads (length = 1.35 × width)
    "corner_radius_px": 6,
    "recompute_delay_ms": 120,      # wait after zoom/pan before streamlines are recomputed
    "wall_width": 3.0,              # px
    "wall_hatch_count": 70,         # hatch marks per view diagonal
    # selected element glows in its own color: (extra size in px, opacity 0–255), outermost first
    "selection_glow": ((26, 28), (17, 55), (9, 95)),
}

# ---------------------------------------------------------------------------
# Element markers on the plot (symbol names from pyqtgraph: o, d, s, t, +, x ...)
# "filled": False draws only the outline (ring).
# ---------------------------------------------------------------------------
MARKERS = {
    "source":  {"symbol": "o", "size": 11, "filled": True},     # sink uses color el_sink
    "vortex":  {"symbol": "o", "size": 18, "filled": False},
    "doublet": {"symbol": "d", "size": 13, "filled": True},
    "sector":  {"symbol": "s", "size": 9, "filled": True},      # vertex of the wedge
    "default": {"symbol": "x", "size": 10, "filled": True},     # any future element type
}


def build_stylesheet(t: dict) -> str:
    """Qt stylesheet generated from the palette `t`."""
    r = LAYOUT["corner_radius_px"]
    return f"""
    QMainWindow, QDialog {{ background: {t['window_bg']}; color: {t['text']}; }}
    QWidget {{ color: {t['text']}; }}

    QMenuBar {{ background: {t['panel_bg']}; border-bottom: 1px solid {t['border']}; padding: 2px 4px; }}
    QMenuBar::item {{ padding: 5px 10px; border-radius: {r}px; background: transparent; }}
    QMenuBar::item:selected {{ background: {t['accent_soft']}; }}
    QMenu {{ background: {t['panel_bg']}; border: 1px solid {t['border']}; padding: 4px; }}
    QMenu::item {{ padding: 6px 26px 6px 22px; border-radius: {r}px; }}
    QMenu::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
    QMenu::item:disabled {{ color: {t['text_muted']}; }}
    QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 8px; }}

    QToolBar#ElementToolbar {{ background: {t['panel_bg']}; border: none;
        border-right: 1px solid {t['border']}; padding: 8px 6px; spacing: 6px; }}
    QToolBar#ElementToolbar QToolButton {{ border-radius: {r + 2}px; padding: 6px; }}
    QToolBar#ElementToolbar QToolButton:hover {{ background: {t['accent_soft']}; }}

    QWidget#CanvasBar {{ background: {t['panel_bg']}; border-bottom: 1px solid {t['border']}; }}
    QWidget#CanvasBar QToolButton {{ border: 1px solid {t['border']}; border-radius: {r}px;
        padding: 4px 10px; background: {t['panel_bg']}; }}
    QWidget#CanvasBar QToolButton:hover {{ background: {t['accent_soft']}; }}
    QWidget#CanvasBar QToolButton:checked {{ background: {t['accent']}; color: {t['accent_text']};
        border-color: {t['accent']}; }}
    QLabel#CanvasTitle {{ font-weight: 600; padding-left: 4px; }}

    QDockWidget {{ titlebar-close-icon: none; }}
    QDockWidget::title {{ background: {t['panel_header']}; padding: 7px 10px;
        border-bottom: 1px solid {t['border']}; font-weight: 600; }}
    QWidget#DockBody {{ background: {t['panel_bg']}; }}

    QTreeWidget {{ background: {t['panel_bg']}; border: 1px solid {t['border']};
        border-radius: {r}px; alternate-background-color: {t['window_bg']}; }}
    QTreeWidget::item {{ padding: 4px 2px; }}
    QTreeWidget::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
    QHeaderView::section {{ background: {t['panel_header']}; border: none;
        border-bottom: 1px solid {t['border']}; padding: 5px; font-weight: 600; }}

    QGroupBox {{ border: 1px solid {t['border']}; border-radius: {r}px; margin-top: 14px;
        padding: 10px 8px 8px 8px; background: {t['panel_bg']}; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px;
        color: {t['text_muted']}; font-weight: 600; }}

    QPushButton {{ border: 1px solid {t['border']}; border-radius: {r}px; padding: 6px 14px;
        background: {t['panel_bg']}; }}
    QPushButton:hover {{ background: {t['accent_soft']}; }}
    QPushButton#Primary {{ background: {t['accent']}; color: {t['accent_text']};
        border-color: {t['accent']}; font-weight: 600; }}
    QPushButton#Primary:hover {{ background: {t['accent_hover']}; }}
    QPushButton#Danger {{ color: {t['danger']}; }}
    QPushButton#DangerPrimary {{ background: {t['danger']}; color: #FFFFFF; border-color: {t['danger']};
        font-weight: 600; }}
    QLabel#IssueBox {{ padding: 6px 8px; border: 1px solid {t['border']}; border-radius: {r}px;
        background: {t['window_bg']}; }}
    QLabel#ErrorBanner {{ padding: 6px 12px; color: #FFFFFF; background: {t['danger']}; font-weight: 600; }}

    QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{ border: 1px solid {t['border']};
        border-radius: {r}px; padding: 4px 6px; background: {t['panel_bg']}; }}
    /* hide the small up/down arrows: mouse wheel and keyboard arrows still change the value */
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none; }}
    QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QLineEdit:focus {{ border-color: {t['accent']}; }}
    QComboBox QAbstractItemView {{ background: {t['panel_bg']}; selection-background-color: {t['accent_soft']}; }}

    QSlider::groove:horizontal {{ height: 4px; background: {t['border']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {t['accent']}; width: 14px; height: 14px;
        margin: -6px 0; border-radius: 7px; }}

    QRadioButton {{ spacing: 8px; }}
    QRadioButton::indicator {{ width: 14px; height: 14px; border-radius: 9px;
        border: 2px solid {t['text_muted']}; background: {t['panel_bg']}; }}
    QRadioButton::indicator:hover {{ border-color: {t['accent']}; }}
    QRadioButton::indicator:checked {{ background: {t['accent']}; border: 2px solid {t['accent']}; }}

    QScrollArea {{ border: none; background: {t['panel_bg']}; }}
    QStatusBar {{ background: {t['panel_bg']}; border-top: 1px solid {t['border']}; }}
    QStatusBar QLabel {{ padding: 0 8px; }}
    QLabel#Muted {{ color: {t['text_muted']}; }}
    QLabel#Formula {{ font-family: "Cambria Math", "STIX Two Math", "Times New Roman", serif;
        font-size: 13pt; padding: 6px; background: {t['window_bg']};
        border: 1px solid {t['border']}; border-radius: {r}px; }}
    QLabel#DialogTitle {{ font-size: 13pt; font-weight: 600; }}
    QLabel#ProbeLabel {{ font-family: "Consolas", "Menlo", monospace; }}
    QToolTip {{ background: {t['panel_bg']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 4px; }}
    """
