"""Barcode Generator page."""
from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox,
                               QSpinBox, QVBoxLayout, QWidget)

from qr_studio import barcode_generator as bg
from qr_studio import export as ex
from .widgets import Card, ColorButton, ImageView, ask_image_path, button, label

SCALES = {"Standard (1x)": 1.0, "High (3x)": 3.0, "Ultra (6x)": 6.0}


class BarcodePage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.record_id: int | None = None
        self.clean = ""
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_preview)

        root = QHBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(16)
        left.addWidget(label("Barcode Generator", "h1"))
        left.addWidget(label("Pick a format and enter the data. It is validated as you type.", "muted", True))

        c1 = Card()
        v1 = QVBoxLayout(c1)
        v1.setContentsMargins(20, 18, 20, 18)
        v1.addWidget(label("Barcode", "h2"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(bg.BARCODE_TYPES)
        self.data = QLineEdit()
        self.data.setPlaceholderText("Barcode data")
        self.hint = label("", "muted", True)
        v1.addWidget(self.type_combo)
        v1.addWidget(self.data)
        v1.addWidget(self.hint)
        left.addWidget(c1)

        c2 = Card()
        v2 = QVBoxLayout(c2)
        v2.setContentsMargins(20, 18, 20, 18)
        v2.addWidget(label("Appearance", "h2"))
        f = QFormLayout()
        self.show_text = QCheckBox("Show numbers below barcode")
        self.show_text.setChecked(True)
        self.mw = QSpinBox()
        self.mw.setRange(1, 10)
        self.mw.setSuffix(" px / bar")
        self.height_sp = QSpinBox()
        self.height_sp.setRange(40, 500)
        self.height_sp.setSuffix(" px")
        self.fg = ColorButton("#000000")
        self.bgc = ColorButton("#FFFFFF")
        self.white = QCheckBox("Use white background")
        self.white.setChecked(True)
        self.scale = QComboBox()
        self.scale.addItems(list(SCALES))
        self.scale.setCurrentIndex(1)
        f.addRow("", self.show_text)
        f.addRow("Bar width", self.mw)
        f.addRow("Height", self.height_sp)
        f.addRow("Bar colour", self.fg)
        f.addRow("Background", self.bgc)
        f.addRow("", self.white)
        f.addRow("Export quality", self.scale)
        v2.addLayout(f)
        left.addWidget(c2)

        c3 = Card()
        v3 = QVBoxLayout(c3)
        v3.setContentsMargins(20, 18, 20, 18)
        v3.addWidget(label("Save", "h2"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Name (optional) - used as the file name")
        v3.addWidget(self.name)
        row = QHBoxLayout()
        self.export_btn = button("Export...", primary=True)
        self.save_btn = button("Save to library")
        self.copy_btn = button("Copy image")
        for b in (self.export_btn, self.save_btn, self.copy_btn):
            row.addWidget(b)
        v3.addLayout(row)
        left.addWidget(c3)
        left.addStretch()
        lw = QWidget()
        lw.setLayout(left)
        lw.setMinimumWidth(460)
        lw.setMaximumWidth(520)
        root.addWidget(lw)

        right = Card()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(24, 20, 24, 20)
        rv.addWidget(label("Live preview", "h2"))
        self.preview = ImageView("Enter barcode data to see a preview")
        rv.addWidget(self.preview, 1)
        self.status = label("", "muted", True)
        rv.addWidget(self.status)
        root.addWidget(right, 1)

        self.type_combo.currentIndexChanged.connect(self._type_changed)
        self.data.textChanged.connect(self.schedule)
        for w in (self.show_text,):
            w.toggled.connect(self.schedule)
        self.mw.valueChanged.connect(self.schedule)
        self.height_sp.valueChanged.connect(self.schedule)
        self.fg.changed.connect(self.schedule)
        self.bgc.changed.connect(self.schedule)
        self.white.toggled.connect(self._white)
        self.export_btn.clicked.connect(self.export)
        self.save_btn.clicked.connect(self.save_to_library)
        self.copy_btn.clicked.connect(self.copy_image)
        ctx.settings_changed.connect(self.apply_defaults)
        self.apply_defaults()
        self._type_changed()

    def apply_defaults(self) -> None:
        s = self.ctx.settings
        self.mw.setValue(int(s.get("barcode_module_width")))
        self.height_sp.setValue(int(s.get("barcode_height")))
        self.fg.set_color(s.get("fg_color"))
        self.bgc.set_color(s.get("bg_color"))
        self._white(self.white.isChecked())

    def _white(self, on: bool) -> None:
        self.bgc.setEnabled(not on)
        self.schedule()

    def _type_changed(self) -> None:
        self.hint.setText(bg.HINTS[self.type_combo.currentText()])
        self.record_id = None
        self.schedule()

    def bg_color(self) -> str:
        return "#FFFFFF" if self.white.isChecked() else self.bgc.color()

    def options(self) -> dict:
        return {"module_width": self.mw.value(), "height": self.height_sp.value(), "show_text": self.show_text.isChecked(),
                "fg": self.fg.color(), "bg": self.bg_color()}

    def schedule(self, *_a) -> None:
        self.timer.start()

    def _msg(self, text: str, error: bool = False) -> None:
        self.status.setObjectName("errText" if error else "muted")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(text)

    def update_preview(self) -> None:
        kind, raw = self.type_combo.currentText(), self.data.text()
        if not raw.strip():
            self.clean = ""
            self.preview.clear_image("Enter barcode data to see a preview")
            self._msg("")
            return
        try:
            self.clean = bg.validate(kind, raw)
            o = self.options()
            img = bg.render_barcode(kind, self.clean, o["module_width"], o["height"], o["show_text"], o["fg"], o["bg"])
        except (ValueError, RuntimeError) as e:
            self.clean = ""
            self.preview.clear_image("")
            self._msg(str(e), error=True)
            return
        self.preview.set_image(img)
        self._msg(f"Valid {kind}. Encoded: {self.clean}" if self.clean != raw.strip() else f"Valid {kind}.")

    def _ready(self) -> bool:
        if not self.clean:
            QMessageBox.information(self, "QR Studio", "Enter valid barcode data first.")
            return False
        return True

    def _default_name(self) -> str:
        return self.name.text().strip() or f"{self.type_combo.currentText()} {self.clean}"

    def _store(self, export_path: str = "") -> None:
        if self.record_id:
            if export_path:
                self.ctx.db.update_code_export(self.record_id, export_path)
        else:
            self.record_id = self.ctx.db.add_code(self._default_name(), "barcode", self.type_combo.currentText(),
                                                  self.clean, json.dumps(self.options()), export_path)
        self.ctx.codes_changed.emit()

    def save_to_library(self) -> None:
        if not self._ready():
            return
        self.record_id = None
        self._store()
        self.ctx.db.bump_stat("barcode_generated")
        self.ctx.codes_changed.emit()
        self._msg("Saved to Saved Codes.")

    def export(self) -> None:
        if not self._ready():
            return
        path = ask_image_path(self, self.ctx.settings, ex.safe_filename(self._default_name()), "Export barcode")
        if not path:
            return
        o = self.options()
        try:
            ex.export_barcode(self.type_combo.currentText(), self.clean, path, o["module_width"], o["height"],
                              o["show_text"], o["fg"], o["bg"], SCALES[self.scale.currentText()])
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._store(str(path))
        self.ctx.db.bump_stat("barcode_generated")
        self.ctx.codes_changed.emit()
        self._msg(f"Saved: {path}")

    def copy_image(self) -> None:
        pm = self.preview.pixmap_copy()
        if pm is not None and self.clean:
            QApplication.clipboard().setPixmap(pm)
            self._msg("Image copied to the clipboard.")

    def load_record(self, rec: dict) -> None:
        o = json.loads(rec.get("options") or "{}")
        self.type_combo.blockSignals(True)
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findText(rec["code_type"])))
        self.type_combo.blockSignals(False)
        self.hint.setText(bg.HINTS[self.type_combo.currentText()])
        self.data.setText(rec["data"])
        self.show_text.setChecked(bool(o.get("show_text", True)))
        self.mw.setValue(int(o.get("module_width", 3)))
        self.height_sp.setValue(int(o.get("height", 120)))
        self.fg.set_color(o.get("fg", "#000000"))
        self.white.setChecked(o.get("bg", "#FFFFFF").upper() == "#FFFFFF")
        self.bgc.set_color(o.get("bg", "#FFFFFF"))
        self.name.setText(rec["name"])
        self.update_preview()
        self.record_id = rec["id"]
