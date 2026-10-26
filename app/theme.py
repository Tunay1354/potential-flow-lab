"""
theme.py — ALL visual decisions live here.

To revise the look of the program, change values in this file only:
  * LIGHT / DARK  -> colors ("drafting paper" theme: wooden header, ruler menu rail, paper panels)
  * FONT          -> font families and sizes (the fonts themselves are in assets/fonts, SIL OFL)
  * LAYOUT        -> sizes of the header, panels, icons, window, etc.
Nothing else in the code contains hard-coded colors or sizes.
"""
import os

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------
LIGHT = {
    "name": "light",
    # paper, panels, lines
    "window_bg":    "#EFE8D8",   # drafting paper behind everything
    "paper_grid":   "#3A332610",  # faint 24 px grid on the paper (#RRGGBBAA)
    "panel_bg":     "#FBF7EC",   # panels, plot card, menus
    "panel_header": "#F4EEDF",   # hover of tool buttons, header of tables
    "border":       "#3A3326",   # outer line of panels
    "border_inner": "#9C907A",   # inner line of the double panel frame
    "border_soft":  "#C9BFA9",   # separators inside panels
    "ink":          "#211A12",   # strongest lines (plot card frame, heading rules)
    "text":         "#211A12",
    "text_muted":   "#4E4434",
    "text_disabled": "#6E6452",
    "accent":       "#8A4A12",   # rust: readable as text on paper
    "accent_strong": "#A65A17",  # rust fill (logo, primary buttons)
    "accent_hover": "#B8692A",
    "accent_soft":  "#F0E3C9",   # selected rows, hover
    "accent_text":  "#FBF7EC",   # text on accent / ink fills
    "toggle_on_bg": "#211A12",   # checked tool buttons (Static, Select ...)
    "toggle_on_text": "#FBF7EC",
    "danger":       "#B03A2E",
    # header: wooden plank (logo, name) and the ruler that carries the menus
    "plank":        "#A98B6D",   # "smoked oak"
    "plank_text":   "#211A12",
    "plank_text_muted": "#2A1F15",
    "plank_edge":   "#6E5640",
    "plank_grain_light": "#FFFFFF14",
    "plank_grain_dark":  "#3C281617",
    "ruler":        "#E9D9BE",
    "ruler_tick":   "#5A4330",
    "ruler_text":   "#211A12",
    "ruler_edge":   "#8C6A45",
    "status_bg":    "#E5DCC7",
    # plot
    "plot_bg":      "#FBF7EC",
    "plot_grid":    "#E7E0D0",
    "plot_axis":    "#3A3326",
    "streamline":   "#23395F",
    "dividing_streamline": "#211A12",
    "stagnation":   "#211A12",   # ring of a stagnation point marker
    "body_fill":    "#E6DCC6",
    "body_edge":    "#3A3326",
    # element colors (toolbar icons, list icons, plot markers)
    "el_uniform":   "#2E6491",
    "el_source":    "#B8432F",
    "el_sink":      "#2F7FA8",
    "el_vortex":    "#6E4690",
    "el_doublet":   "#B8641E",
    "el_sector":    "#4F7A3A",
    "el_wall":      "#4A4136",
    "check_icon":   "check_light.svg",
}

DARK = {
    "name": "dark",
    "window_bg":    "#191512",
    "paper_grid":   "#E8DCC80C",
    "panel_bg":     "#221C17",
    "panel_header": "#2B231D",
    "border":       "#8C7B66",
    "border_inner": "#4A3F33",
    "border_soft":  "#3E352C",
    "ink":          "#CFC3AE",
    "text":         "#EDE3D2",
    "text_muted":   "#B5A690",
    "text_disabled": "#A39582",
    "accent":       "#E08A47",
    "accent_strong": "#E08A47",
    "accent_hover": "#F0A86E",
    "accent_soft":  "#3A2D22",
    "accent_text":  "#191512",
    "toggle_on_bg": "#EDE3D2",
    "toggle_on_text": "#191512",
    "danger":       "#E57368",
    "plank":        "#4E3C2C",
    "plank_text":   "#F3EAD9",
    "plank_text_muted": "#D8C8B0",
    "plank_edge":   "#2A2018",
    "plank_grain_light": "#FFEBD20B",
    "plank_grain_dark":  "#00000029",
    "ruler":        "#2F271F",
    "ruler_tick":   "#A8957C",
    "ruler_text":   "#EDE3D2",
    "ruler_edge":   "#5E4D3C",
    "status_bg":    "#14110E",
    "plot_bg":      "#1D1915",
    "plot_grid":    "#2E2822",
    "plot_axis":    "#CFC3AE",
    "streamline":   "#9EC6EA",
    "dividing_streamline": "#F3EAD9",
    "stagnation":   "#F3EAD9",
    "body_fill":    "#2E2720",
    "body_edge":    "#CFC3AE",
    "el_uniform":   "#6FA6DA",
    "el_source":    "#F07F67",
    "el_sink":      "#6BBFE0",
    "el_vortex":    "#C9A8EA",
    "el_doublet":   "#E8A25E",
    "el_sector":    "#8CC27A",
    "el_wall":      "#B5A690",
    "check_icon":   "check_dark.svg",
}

DEFAULT_THEME = LIGHT

# ---------------------------------------------------------------------------
# Fonts (bundled in assets/fonts; the first available family of each list is used)
# ---------------------------------------------------------------------------
FONT = {
    "families": ["Barlow", "Segoe UI", "Helvetica Neue", "Arial"],        # general text
    "mono": ["IBM Plex Mono", "Consolas", "Menlo", "Courier New"],         # numbers, labels, title
    "heading": ["Barlow Condensed", "Arial Narrow", "Segoe UI"],          # menus, panel headings, buttons
    "size_pt": 10.5,
    "mono_size_pt": 9.5,
    "menu_size_pt": 11.5,            # File / Edit ... on the ruler (shown in capitals)
    "heading_size_pt": 9.5,          # panel headings (capitals, wide letter spacing)
    "button_size_pt": 10,            # tool buttons above the plot (capitals)
    "title_size_pt": 14,             # "POTENTIAL FLOW LAB" on the plank
    "plot_label_size_pt": 10,
}

# ---------------------------------------------------------------------------
# Layout / sizes
# ---------------------------------------------------------------------------
LAYOUT = {
    "window_title": "Potential Flow Lab",
    "window_size": (1400, 860),     # size when the window is not maximized
    "start_maximized": True,
    "plank_height": 58,             # wooden header with logo and name
    "ruler_height": 38,             # ruler under it that carries the menus
    "logo_px": 36,
    # free space right of the Help menu: the beaver mascot will hang there later (head over the
    # ruler's top edge, paws on the ruler, body behind it) — see ROADMAP, Faz 6
    "beaver_perch_px": 120,
    "gap": 16,                      # paper visible between the header, panels, plot and status bar
    "paper_grid_px": 24,
    "toolbar_icon_px": 30,
    "toolbar_show_text": True,      # element names under the toolbar icons
    "right_panel_width": 340,
    "elements_panel_min_height": 210,
    "plot_initial_range": {"x": (-4.0, 4.0), "y": (-2.6, 2.6)},
    "streamline_width": 1.4,
    "dividing_streamline_width": 2.4,
    "arrow_size_px": 6.5,           # width of the streamline arrow heads (length = 1.35 × width)
    "corner_radius_px": 0,          # drafting look: square corners
    "wall_width": 3.0,              # px
    "wall_hatch_count": 70,         # hatch marks per view diagonal
    # selected element glows in its own color: (extra size in px, opacity 0–255), outermost first
    "selection_glow": ((26, 28), (17, 55), (9, 95)),
    "pick_radius_px": 10,           # a click this close (in screen pixels) to a symbol or wall selects it
    "stagnation_label_offset_px": 14,   # the x / y box of a selected stagnation point sits this far away
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
    "stagnation": {"symbol": "stagnation", "size": 15, "filled": False},  # ring with a cross (⊗), not an element
    "default": {"symbol": "x", "size": 10, "filled": True},     # any future element type
}


def first_family(key: str) -> str:
    """First installed family of FONT[key] (after the bundled fonts were loaded)."""
    from PySide6.QtGui import QFontDatabase
    have = set(QFontDatabase.families())
    for fam in FONT[key]:
        if fam in have:
            return fam
    return FONT[key][-1]


def build_stylesheet(t: dict) -> str:
    """Qt stylesheet generated from the palette `t`. Capitals and letter spacing (which style sheets
    cannot do) are set on the fonts in chrome.py."""
    mono, head = first_family("mono"), first_family("heading")
    check = os.path.join(ASSETS_DIR, "icons", t["check_icon"]).replace("\\", "/")
    return f"""
    QMainWindow, QDialog {{ background: {t['window_bg']}; color: {t['text']}; }}
    QWidget {{ color: {t['text']}; }}
    QMainWindow::separator {{ width: 4px; height: 4px; background: transparent; }}

    QMenuBar#RulerMenu {{ background: transparent; border: none; padding: 0; spacing: 2px; }}
    QMenuBar#RulerMenu::item {{ color: {t['ruler_text']}; padding: 5px 12px; margin-top: 2px;
        background: transparent; }}
    QMenuBar#RulerMenu::item:selected, QMenuBar#RulerMenu::item:pressed {{
        background: {t['accent_soft']}; color: {t['text']}; }}
    QMenu {{ background: {t['panel_bg']}; border: 1px solid {t['border']}; padding: 4px; }}
    QMenu::item {{ padding: 6px 26px 6px 22px; }}
    QMenu::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
    QMenu::item:disabled {{ color: {t['text_disabled']}; }}
    QMenu::separator {{ height: 1px; background: {t['border_soft']}; margin: 4px 8px; }}
    QLabel#PlankTitle {{ color: {t['plank_text']}; }}
    QLabel#PlankMuted {{ color: {t['plank_text_muted']}; font-family: "{mono}"; }}
    QLabel#RulerScale {{ color: {t['ruler_text']}; font-family: "{mono}"; }}

    QToolBar#ElementToolbar {{ background: {t['panel_bg']}; border: 1px solid {t['border']};
        margin: 0 0 {16}px 16px; padding: 6px 4px; spacing: 2px; }}
    QToolBar#ElementToolbar QToolButton {{ padding: 5px 2px; border: 1px solid transparent; color: {t['text']}; }}
    QToolBar#ElementToolbar QToolButton:hover {{ background: {t['panel_header']}; border-color: {t['border']}; }}
    QToolBar#ElementToolbar::separator {{ height: 1px; background: {t['border_soft']}; margin: 6px 10px; }}
    QLabel#ToolbarHeading {{ color: {t['text']}; padding: 4px 0 6px 0; }}

    QWidget#CanvasBar {{ background: {t['panel_bg']}; border-bottom: 1px solid {t['ink']}; }}
    QWidget#CanvasBar QToolButton {{ border: 1px solid {t['border']}; padding: 4px 10px;
        background: {t['panel_bg']}; color: {t['text']}; }}
    QWidget#CanvasBar QToolButton:hover {{ background: {t['accent_soft']}; }}
    QWidget#CanvasBar QToolButton:checked {{ background: {t['toggle_on_bg']}; color: {t['toggle_on_text']};
        border-color: {t['toggle_on_bg']}; }}
    QWidget#CanvasBar QToolButton#Export {{ color: {t['accent']}; border-color: {t['accent']}; }}
    QWidget#TitleBlock {{ background: {t['panel_bg']}; border-top: 1px solid {t['ink']}; }}
    QWidget#TitleCell {{ border-right: 1px solid {t['ink']}; }}
    QWidget#TitleCellLast {{ border: none; }}
    QLabel#TitleKey {{ color: {t['text_muted']}; font-family: "{mono}"; font-size: 7.5pt; }}
    QLabel#TitleValue {{ color: {t['text']}; font-family: "{mono}"; font-size: 9pt; }}

    QDockWidget {{ titlebar-close-icon: none; color: {t['text']}; }}
    QWidget#DockBody {{ background: {t['panel_bg']}; }}
    QLabel#PanelHeading {{ color: {t['text']}; }}
    QLabel#PanelNote {{ color: {t['text_muted']}; font-family: "{mono}"; font-size: 8pt; }}

    QTreeWidget {{ background: {t['panel_bg']}; border: none; outline: none; }}
    QTreeWidget::item {{ padding: 5px 2px; border-bottom: 1px solid {t['border_soft']}; }}
    QTreeWidget::item:selected {{ background: {t['accent_soft']}; color: {t['text']}; }}
    QTreeWidget::item:hover {{ background: {t['panel_header']}; }}
    QHeaderView::section {{ background: {t['panel_bg']}; border: none;
        border-bottom: 1px solid {t['border_soft']}; padding: 4px; color: {t['text_muted']};
        font-family: "{mono}"; font-size: 8pt; }}

    QGroupBox {{ border: none; border-top: 1px solid {t['border_soft']}; margin-top: 18px;
        padding: 12px 2px 4px 2px; background: transparent; font-family: "{head}"; font-weight: 700;
        font-size: 10pt; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 0px; padding: 0 0; color: {t['text']}; }}

    QPushButton {{ border: 1px solid {t['border']}; padding: 5px 12px; background: {t['panel_bg']};
        color: {t['text']}; }}
    QPushButton:hover {{ background: {t['accent_soft']}; }}
    QPushButton:disabled {{ color: {t['text_disabled']}; border-color: {t['border_soft']}; }}
    QPushButton#Primary {{ background: {t['accent_strong']}; color: {t['accent_text']};
        border-color: {t['ink']}; font-weight: 600; }}
    QPushButton#Primary:hover {{ background: {t['accent_hover']}; }}
    QPushButton#Danger {{ color: {t['danger']}; }}
    QPushButton#Danger:disabled {{ color: {t['text_disabled']}; }}
    QPushButton#DangerPrimary {{ background: {t['danger']}; color: #FFFFFF; border-color: {t['danger']};
        font-weight: 600; }}
    QLabel#IssueBox {{ padding: 6px 8px; border: 1px solid {t['border_soft']}; background: {t['window_bg']}; }}
    QLabel#ErrorBanner {{ padding: 6px 12px; color: #FFFFFF; background: {t['danger']}; font-weight: 600; }}

    QLineEdit, QDoubleSpinBox, QSpinBox {{ border: none; border-bottom: 1px solid {t['border']};
        padding: 3px 4px; background: transparent; font-family: "{mono}"; selection-background-color: {t['accent_soft']};
        selection-color: {t['text']}; }}
    QComboBox {{ border: 1px solid {t['border']}; padding: 3px 6px; background: {t['panel_bg']}; }}
    QDialog QLineEdit, QDialog QDoubleSpinBox, QDialog QSpinBox {{ background: {t['panel_bg']}; }}
    /* hide the small up/down arrows: mouse wheel and keyboard arrows still change the value */
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none; }}
    QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-bottom: 2px solid {t['accent']}; }}
    QComboBox:focus {{ border-color: {t['accent']}; }}
    QComboBox QAbstractItemView {{ background: {t['panel_bg']}; border: 1px solid {t['border']};
        selection-background-color: {t['accent_soft']}; selection-color: {t['text']}; }}

    QCheckBox {{ spacing: 9px; }}
    QCheckBox::indicator, QTreeWidget::indicator {{ width: 13px; height: 13px; border: 1px solid {t['border']};
        background: {t['panel_bg']}; }}
    QCheckBox::indicator:checked, QTreeWidget::indicator:checked {{ image: url("{check}"); border: none;
        width: 15px; height: 15px; }}
    QCheckBox::indicator:disabled {{ border-color: {t['border_soft']}; }}
    QCheckBox:disabled {{ color: {t['text_disabled']}; }}

    QSlider::groove:horizontal {{ height: 2px; background: {t['border_inner']}; }}
    QSlider::sub-page:horizontal {{ background: {t['accent']}; }}
    QSlider::handle:horizontal {{ background: {t['panel_bg']}; border: 2px solid {t['accent']}; width: 10px;
        height: 10px; margin: -6px 0; }}

    QRadioButton {{ spacing: 8px; }}
    QRadioButton::indicator {{ width: 12px; height: 12px; border-radius: 8px;
        border: 2px solid {t['text_muted']}; background: {t['panel_bg']}; }}
    QRadioButton::indicator:hover {{ border-color: {t['accent']}; }}
    QRadioButton::indicator:checked {{ background: {t['accent']}; border: 2px solid {t['accent']}; }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ width: 8px; background: transparent; margin: 0; }}
    QScrollBar:horizontal {{ height: 8px; background: transparent; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {t['border_inner']}; min-height: 30px; }}
    QScrollBar::handle:horizontal {{ background: {t['border_inner']}; min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QStatusBar {{ background: {t['status_bg']}; border-top: 1px solid {t['border']}; color: {t['text']};
        font-family: "{mono}"; font-size: 9pt; }}
    QStatusBar::item {{ border: none; }}
    QStatusBar QLabel {{ padding: 0 10px; font-family: "{mono}"; font-size: 9pt; }}
    QLabel#Muted {{ color: {t['text_muted']}; }}
    QLabel#Formula {{ font-family: "Cambria Math", "STIX Two Math", "Times New Roman", serif;
        font-size: 13pt; padding: 6px; background: {t['window_bg']}; border: 1px solid {t['border_soft']}; }}
    QLabel#DialogTitle {{ font-size: 13pt; font-weight: 600; }}
    QLabel#ProbeLabel {{ font-family: "{mono}"; }}
    QToolTip {{ background: {t['panel_bg']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 4px; }}
    """
