"""Reusable widgets and helpers."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QColorDialog, QFileDialog, QFrame, QHeaderView, QLabel, QPushButton,
                               QSizePolicy, QTableWidget, QTableWidgetItem)

from qr_studio.export import FILTERS, FORMATS
from . import theme


def pil_to_qimage(img) -> QImage:
    img = img.convert("RGBA")
    qimg = QImage(img.tobytes("raw", "RGBA"), img.width, img.height, QImage.Format.Format_RGBA8888)
    return qimg.copy()


def pil_to_qpixmap(img) -> QPixmap:
    return QPixmap.fromImage(pil_to_qimage(img))


class Card(QFrame):
    def __init__(self, shadow: bool = True):
        super().__init__()
        self.setObjectName("card")
        if shadow:
            theme.add_shadow(self)


def label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def button(text: str, primary: bool = False, danger: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        b.setProperty("primary", True)
    if danger:
        b.setProperty("danger", True)
    return b


class ColorButton(QPushButton):
    changed = Signal(str)

    def __init__(self, color: str = "#000000"):
        super().__init__()
        self._c = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._pick)
        self._paint()

    def color(self) -> str:
        return self._c

    def set_color(self, c: str) -> None:
        self._c = QColor(c).name().upper() if QColor(c).isValid() else self._c
        self._paint()

    def _pick(self) -> None:
        col = QColorDialog.getColor(QColor(self._c), self, "Choose colour")
        if col.isValid():
            self.set_color(col.name())
            self.changed.emit(self._c)

    def _paint(self) -> None:
        fg = "#000000" if QColor(self._c).lightness() > 140 else "#FFFFFF"
        self.setText(self._c)
        self.setStyleSheet(f"QPushButton {{ background:{self._c}; color:{fg}; border:1px solid #999999; border-radius:10px; padding:7px 10px; }}")


class ImageView(QLabel):
    """Shows a PIL image scaled to fit, keeping its aspect ratio."""

    def __init__(self, placeholder: str = ""):
        super().__init__(placeholder)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(160, 160)
        self._pm: QPixmap | None = None

    def set_image(self, pil_img) -> None:
        self._pm = pil_to_qpixmap(pil_img)
        self._refresh()

    def set_qimage(self, qimg: QImage) -> None:
        self._pm = QPixmap.fromImage(qimg)
        self._refresh()

    def pixmap_copy(self) -> QPixmap | None:
        return self._pm

    def clear_image(self, text: str = "") -> None:
        self._pm = None
        self.setPixmap(QPixmap())
        self.setText(text)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._refresh()

    def _refresh(self) -> None:
        if self._pm is not None:
            self.setPixmap(self._pm.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))


def make_table(headers: list[str], stretch: int = -1, multi: bool = True) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if multi else QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setWordWrap(False)
    t.verticalHeader().setDefaultSectionSize(38)
    hh = t.horizontalHeader()
    hh.setHighlightSections(False)
    hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    hh.setStretchLastSection(stretch < 0)
    if stretch >= 0:
        hh.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    return t


def set_row(table: QTableWidget, row: int, values: list, data=None) -> None:
    for c, v in enumerate(values):
        it = QTableWidgetItem("" if v is None else str(v))
        if c == 0 and data is not None:
            it.setData(Qt.ItemDataRole.UserRole, data)
        table.setItem(row, c, it)


def selected_ids(table: QTableWidget) -> list[int]:
    ids = []
    for idx in table.selectionModel().selectedRows():
        it = table.item(idx.row(), 0)
        if it is not None and it.data(Qt.ItemDataRole.UserRole) is not None:
            ids.append(int(it.data(Qt.ItemDataRole.UserRole)))
    return ids


def ask_image_path(parent, settings, base_name: str, title: str = "Export") -> Path | None:
    """Save As dialog for PNG/JPG/JPEG/SVG/PDF. Returns the chosen path (with extension) or None."""
    default_fmt = settings.get("default_format")
    default_fmt = default_fmt if default_fmt in FORMATS else "PNG"
    start = str(Path(settings.get("download_dir")) / f"{base_name}.{default_fmt.lower()}")
    path, chosen = QFileDialog.getSaveFileName(parent, title, start, ";;".join(FILTERS[f] for f in FORMATS), FILTERS[default_fmt])
    if not path:
        return None
    p = Path(path)
    if p.suffix.lower() not in tuple("." + f.lower() for f in FORMATS):
        ext = next((f.lower() for f in FORMATS if FILTERS[f] == chosen), default_fmt.lower())
        p = p.with_name(p.name + "." + ext)
    return p
