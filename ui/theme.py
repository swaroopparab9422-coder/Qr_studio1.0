"""Swiss Cream minimal theme (cream 60% / petrol ink 30% / persimmon accent 10%) + a dark variant."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect

PALETTES = {
    "Swiss Cream": dict(bg="#F0EBD8", sidebar="#24505A", side_text="#C9D6D3", side_hover="#2F5E69", card="#F8F5EA",
                        card2="#F0EBD8", input="#FFFFFF", border="#DDD5BF", text="#1D3A41", muted="#5D6F6E",
                        accent="#FF5A1E", accent_hover="#E84E15", secondary="#24505A", on_accent="#FFFFFF",
                        on_secondary="#F7F3E6", chip="#E6E0CB", ok="#2E7D5B", danger="#C0392B",
                        shadow="#1D3A41", shadow_alpha=40),
    "Petrol Night": dict(bg="#15323A", sidebar="#0F252B", side_text="#A9BFBD", side_hover="#1B3D46", card="#1C4049",
                         card2="#173740", input="#102A31", border="#2F5963", text="#F0EBD8", muted="#A9BFBD",
                         accent="#FF5A1E", accent_hover="#FF7440", secondary="#2F5963", on_accent="#FFFFFF",
                         on_secondary="#F0EBD8", chip="#24505A", ok="#4FD1A1", danger="#FF8A7A",
                         shadow="#000000", shadow_alpha=110),
}
_current = dict(PALETTES["Swiss Cream"])
_name = "Swiss Cream"
_effects: list[QGraphicsDropShadowEffect] = []


def palette() -> dict:
    return _current


def theme_names() -> list[str]:
    return list(PALETTES)


def add_shadow(widget, blur: int = 24, dy: int = 4) -> None:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    _paint_effect(eff)
    widget.setGraphicsEffect(eff)
    _effects.append(eff)


def _paint_effect(eff) -> None:
    c = QColor(_current["shadow"])
    c.setAlpha(_current["shadow_alpha"])
    eff.setColor(c)


def apply_theme(app, name: str) -> None:
    global _name
    _name = name if name in PALETTES else "Swiss Cream"
    _current.clear()
    _current.update(PALETTES[_name])
    app.setStyleSheet(build_qss(_current))
    alive = []
    for e in _effects:
        try:
            _paint_effect(e)
            alive.append(e)
        except RuntimeError:  # underlying C++ object was deleted
            pass
    _effects[:] = alive


def build_qss(p: dict) -> str:
    return f"""
QWidget {{ color:{p['text']}; font-family:'Segoe UI','Inter',sans-serif; font-size:10pt; }}
QMainWindow, QDialog, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background:{p['bg']}; }}
QToolTip {{ background:{p['secondary']}; color:{p['on_secondary']}; border:none; padding:6px; }}
QLabel {{ background:transparent; }}
#sidebar {{ background:{p['sidebar']}; }}
#sidebar QLabel {{ color:{p['on_secondary']}; }}
#brand {{ font-size:16pt; font-weight:700; color:#F7F3E6; }}
#sideNote {{ background:{p['side_hover']}; border-radius:12px; padding:12px; color:{p['side_text']}; font-size:9pt; }}
QPushButton#nav {{ text-align:left; padding:11px 14px; border:none; border-radius:12px; color:{p['side_text']}; background:transparent; font-weight:500; }}
QPushButton#nav:hover {{ background:{p['side_hover']}; color:#FFFFFF; }}
QPushButton#nav:checked {{ background:{p['accent']}; color:#FFFFFF; }}
#h1 {{ font-size:22pt; font-weight:700; color:{p['text']}; }}
#h2 {{ font-size:12.5pt; font-weight:700; color:{p['text']}; }}
#muted {{ color:{p['muted']}; }}
#bigNum {{ font-size:26pt; font-weight:700; color:{p['text']}; }}
#accentNum {{ font-size:22pt; font-weight:700; color:{p['accent']}; }}
#okText {{ color:{p['ok']}; font-weight:600; }}
#errText {{ color:{p['danger']}; font-weight:600; }}
#chip {{ background:{p['card']}; border:1px solid {p['border']}; border-radius:15px; padding:6px 14px; color:{p['secondary'] if p['bg']=='#F0EBD8' else p['text']}; font-weight:600; }}
#card {{ background:{p['card']}; border:1px solid {p['border']}; border-radius:16px; }}
#tile {{ background:{p['card2']}; border:1px solid {p['border']}; border-radius:14px; text-align:left; padding:14px; }}
#tile:hover {{ border:1px solid {p['accent']}; }}
#resultBox {{ background:{p['secondary']}; border-radius:14px; }}
#resultBox QLabel {{ color:{p['on_secondary']}; }}
#resultText {{ font-size:15pt; font-weight:600; color:{p['on_secondary']}; }}
#scanInput {{ background:#FFFFFF; color:#1D3A41; border:2px solid {p['accent']}; border-radius:14px; padding:14px 16px; font-size:15pt; }}
QPushButton {{ background:{p['card2']}; border:1px solid {p['border']}; border-radius:10px; padding:9px 16px; font-weight:600; }}
QPushButton:hover {{ border:1px solid {p['accent']}; }}
QPushButton:disabled {{ color:{p['muted']}; background:{p['chip']}; }}
QPushButton[primary="true"] {{ background:{p['accent']}; border:1px solid {p['accent']}; color:{p['on_accent']}; }}
QPushButton[primary="true"]:hover {{ background:{p['accent_hover']}; }}
QPushButton[danger="true"] {{ color:{p['danger']}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background:{p['input']}; color:{'#1D3A41' if p['bg']=='#F0EBD8' else p['text']}; border:1px solid {p['border']}; border-radius:10px; padding:7px 10px; selection-background-color:{p['accent']}; selection-color:#FFFFFF; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border:1px solid {p['accent']}; }}
QComboBox QAbstractItemView {{ background:{p['card']}; color:{p['text']}; border:1px solid {p['border']}; selection-background-color:{p['accent']}; selection-color:#FFFFFF; }}
QCheckBox {{ spacing:8px; }}
QCheckBox::indicator {{ width:18px; height:18px; border-radius:5px; border:1px solid {p['border']}; background:{p['input']}; }}
QCheckBox::indicator:checked {{ background:{p['accent']}; border:1px solid {p['accent']}; }}
QTableWidget {{ background:{p['card']}; alternate-background-color:{p['card2']}; border:1px solid {p['border']}; border-radius:12px; gridline-color:transparent; selection-background-color:{p['accent']}; selection-color:#FFFFFF; }}
QTableWidget::item {{ padding:4px 8px; }}
QHeaderView::section {{ background:{p['card2']}; color:{p['muted']}; padding:8px; border:none; border-bottom:1px solid {p['border']}; font-weight:600; }}
QProgressBar {{ background:{p['chip']}; border:none; border-radius:8px; height:14px; text-align:center; }}
QProgressBar::chunk {{ background:{p['accent']}; border-radius:8px; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:{p['border']}; border-radius:5px; min-height:30px; }}
QScrollBar:horizontal {{ background:transparent; height:10px; margin:0; }}
QScrollBar::handle:horizontal {{ background:{p['border']}; border-radius:5px; min-width:30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QMessageBox {{ background:{p['bg']}; }}
"""
