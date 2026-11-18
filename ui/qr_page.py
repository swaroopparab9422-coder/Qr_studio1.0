"""QR Code Generator page."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
                               QMessageBox, QPlainTextEdit, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from qr_studio import export as ex
from qr_studio import qr_generator as qg
from . import theme
from .widgets import Card, ColorButton, ImageView, ask_image_path, button, label

PREVIEW_PX = 600


class QrPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.logo_path = ""
        self.record_id: int | None = None
        self.payload = ""
        self.widgets: dict[str, QWidget] = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.update_preview)

        root = QHBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        # ---- left: form
        left_host = QWidget()
        lv = QVBoxLayout(left_host)
        lv.setContentsMargins(0, 0, 8, 0)
        lv.setSpacing(16)
        lv.addWidget(label("QR Code Generator", "h1"))
        lv.addWidget(label("Choose a type, fill in the details - the preview updates instantly.", "muted", True))

        c1 = Card()
        v1 = QVBoxLayout(c1)
        v1.setContentsMargins(20, 18, 20, 18)
        v1.addWidget(label("Type", "h2"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(qg.QR_TYPES))
        self.type_combo.currentIndexChanged.connect(self._rebuild_fields)
        v1.addWidget(self.type_combo)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.form.setContentsMargins(0, 8, 0, 0)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        v1.addWidget(self.form_host)
        lv.addWidget(c1)

        c2 = Card()
        v2 = QVBoxLayout(c2)
        v2.setContentsMargins(20, 18, 20, 18)
        v2.addWidget(label("Appearance", "h2"))
        g = QFormLayout()
        self.size = QSpinBox()
        self.size.setRange(200, 4000)
        self.size.setSingleStep(100)
        self.size.setSuffix(" px")
        self.ec = QComboBox()
        self.ec.addItems(list(qg.EC_LEVELS))
        self.ec.setCurrentIndex(1)
        self.fg = ColorButton("#000000")
        self.bg = ColorButton("#FFFFFF")
        self.white_bg = QCheckBox("Use white background")
        self.white_bg.setChecked(True)
        self.logo_lbl = label("No logo", "muted")
        self.logo_btn = button("Choose logo...")
        self.logo_clear = button("Remove")
        lrow = QHBoxLayout()
        lrow.addWidget(self.logo_btn)
        lrow.addWidget(self.logo_clear)
        lrow.addStretch()
        g.addRow("Size (square)", self.size)
        g.addRow("Error correction", self.ec)
        g.addRow("Foreground", self.fg)
        g.addRow("Background", self.bg)
        g.addRow("", self.white_bg)
        g.addRow("Center logo", lrow)
        g.addRow("", self.logo_lbl)
        v2.addLayout(g)
        lv.addWidget(c2)

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
        lv.addWidget(c3)
        lv.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(left_host)
        scroll.setMinimumWidth(470)
        scroll.setMaximumWidth(540)
        root.addWidget(scroll)

        # ---- right: preview
        right = Card()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(24, 20, 24, 20)
        rv.addWidget(label("Live preview", "h2"))
        self.preview = ImageView("Fill in the form to see your QR code")
        rv.addWidget(self.preview, 1)
        self.status = label("", "muted", True)
        rv.addWidget(self.status)
        self.payload_view = QPlainTextEdit()
        self.payload_view.setReadOnly(True)
        self.payload_view.setMaximumHeight(90)
        rv.addWidget(label("Encoded content", "muted"))
        rv.addWidget(self.payload_view)
        root.addWidget(right, 1)

        self.size.valueChanged.connect(self.schedule)
        self.ec.currentIndexChanged.connect(self.schedule)
        self.fg.changed.connect(self.schedule)
        self.bg.changed.connect(self.schedule)
        self.white_bg.toggled.connect(self._white_toggled)
        self.logo_btn.clicked.connect(self._pick_logo)
        self.logo_clear.clicked.connect(self._clear_logo)
        self.export_btn.clicked.connect(self.export)
        self.save_btn.clicked.connect(self.save_to_library)
        self.copy_btn.clicked.connect(self.copy_image)
        ctx.settings_changed.connect(self.apply_defaults)
        self.apply_defaults()
        self._rebuild_fields()

    # ---- defaults / fields
    def apply_defaults(self) -> None:
        s = self.ctx.settings
        self.size.setValue(int(s.get("qr_size")))
        self.fg.set_color(s.get("fg_color"))
        self.bg.set_color(s.get("bg_color"))
        self._white_toggled(self.white_bg.isChecked())

    def _white_toggled(self, on: bool) -> None:
        self.bg.setEnabled(not on)
        self.schedule()

    def _rebuild_fields(self) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self.widgets.clear()
        for f in qg.QR_TYPES[self.type_combo.currentText()]:
            if f.kind == "multiline":
                w = QPlainTextEdit()
                w.setFixedHeight(84)
                w.setPlaceholderText(f.placeholder)
                w.textChanged.connect(self.schedule)
            elif f.kind == "combo":
                w = QComboBox()
                w.addItems(list(f.options))
                w.currentIndexChanged.connect(self.schedule)
            elif f.kind == "check":
                w = QCheckBox(f.placeholder or "Yes")
                w.toggled.connect(self.schedule)
            else:
                w = QLineEdit()
                w.setPlaceholderText(f.placeholder)
                w.textChanged.connect(self.schedule)
            self.widgets[f.key] = w
            self.form.addRow(f.label + ("" if f.required else " (optional)"), w)
        self.record_id = None
        self.schedule()

    def values(self) -> dict:
        out = {}
        for k, w in self.widgets.items():
            if isinstance(w, QLineEdit):
                out[k] = w.text()
            elif isinstance(w, QPlainTextEdit):
                out[k] = w.toPlainText()
            elif isinstance(w, QComboBox):
                out[k] = w.currentText()
            elif isinstance(w, QCheckBox):
                out[k] = "1" if w.isChecked() else ""
        return out

    def set_values(self, vals: dict) -> None:
        for k, w in self.widgets.items():
            v = vals.get(k, "")
            if isinstance(w, QLineEdit):
                w.setText(v)
            elif isinstance(w, QPlainTextEdit):
                w.setPlainText(v)
            elif isinstance(w, QComboBox):
                i = w.findText(v)
                w.setCurrentIndex(max(0, i))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(v))

    def bg_color(self) -> str:
        return "#FFFFFF" if self.white_bg.isChecked() else self.bg.color()

    def options(self) -> dict:
        return {"qr_type": self.type_combo.currentText(), "fields": self.values(), "size": self.size.value(),
                "fg": self.fg.color(), "bg": self.bg_color(), "ec": qg.EC_LEVELS[self.ec.currentText()],
                "logo": self.logo_path}

    # ---- logo
    def _pick_logo(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Choose logo", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if p:
            self.logo_path = p
            self.logo_lbl.setText(Path(p).name + "  (error correction H is used automatically)")
            self.schedule()

    def _clear_logo(self) -> None:
        self.logo_path = ""
        self.logo_lbl.setText("No logo")
        self.schedule()

    # ---- preview
    def schedule(self, *_a) -> None:
        self.timer.start()

    def _message(self, text: str, error: bool = False) -> None:
        self.status.setObjectName("errText" if error else "muted")
        self.status.setStyleSheet("")  # re-polish
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(text)

    def update_preview(self) -> None:
        o = self.options()
        try:
            self.payload = qg.build_payload(o["qr_type"], o["fields"])
        except ValueError as e:
            self.payload = ""
            self.preview.clear_image("Fill in the form to see your QR code")
            self.payload_view.setPlainText("")
            self._message(str(e), error=bool(any(v for v in o["fields"].values())))
            return
        try:
            img = qg.make_qr_image(self.payload, PREVIEW_PX, o["fg"], o["bg"], o["ec"], o["logo"] or None)
        except (ValueError, RuntimeError) as e:
            self.preview.clear_image("")
            self._message(str(e), error=True)
            return
        self.preview.set_image(img)
        self.payload_view.setPlainText(self.payload)
        notes = qg.scannability_notes(o["fg"], o["bg"], o["logo"], o["ec"], len(self.payload))
        ok = qg.verify_decodable(img, self.payload)
        head = {True: "Verified: this code was read back successfully.", False: "Warning: could not read this code back - try darker colours, a lower error correction or less data.",
                None: ""}[ok]
        self._message(" ".join(filter(None, [head] + notes)), error=(ok is False))

    # ---- actions
    def _ready(self) -> bool:
        if not self.payload:
            QMessageBox.information(self, "QR Studio", "Fill in the form first so there is a QR code to save.")
            return False
        return True

    def _default_name(self) -> str:
        return self.name.text().strip() or f"{self.type_combo.currentText()} {datetime.now():%Y-%m-%d %H%M%S}"

    def _store(self, export_path: str = "") -> None:
        o = self.options()
        if self.record_id:
            if export_path:
                self.ctx.db.update_code_export(self.record_id, export_path)
        else:
            self.record_id = self.ctx.db.add_code(self._default_name(), "qr", o["qr_type"], self.payload, json.dumps(o), export_path)
        self.ctx.codes_changed.emit()

    def save_to_library(self) -> None:
        if not self._ready():
            return
        self.record_id = None
        self._store()
        self.ctx.db.bump_stat("qr_generated")
        self.ctx.codes_changed.emit()
        self._message("Saved to Saved Codes.")

    def export(self) -> None:
        if not self._ready():
            return
        path = ask_image_path(self, self.ctx.settings, ex.safe_filename(self._default_name()), "Export QR code")
        if not path:
            return
        o = self.options()
        try:
            ex.export_qr(self.payload, path, o["size"], o["fg"], o["bg"], o["ec"], o["logo"] or None)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._store(str(path))
        self.ctx.db.bump_stat("qr_generated")
        self.ctx.codes_changed.emit()
        self._message(f"Saved: {path}")

    def copy_image(self) -> None:
        pm = self.preview.pixmap_copy()
        if pm is None or not self.payload:
            return
        QApplication.clipboard().setPixmap(pm)
        self._message("Image copied to the clipboard.")

    def load_record(self, rec: dict) -> None:
        o = json.loads(rec.get("options") or "{}")
        self.type_combo.blockSignals(True)
        i = self.type_combo.findText(o.get("qr_type", rec["code_type"]))
        self.type_combo.setCurrentIndex(max(0, i))
        self.type_combo.blockSignals(False)
        self._rebuild_fields()
        self.set_values(o.get("fields", {}))
        self.size.setValue(int(o.get("size", 1024)))
        self.fg.set_color(o.get("fg", "#000000"))
        bgc = o.get("bg", "#FFFFFF")
        self.white_bg.setChecked(bgc.upper() == "#FFFFFF")
        self.bg.set_color(bgc)
        ec_label = next((k for k, v in qg.EC_LEVELS.items() if v == o.get("ec", "M")), "M (15%)")
        self.ec.setCurrentText(ec_label)
        self.logo_path = o.get("logo", "") if o.get("logo") and Path(o["logo"]).exists() else ""
        self.logo_lbl.setText(Path(self.logo_path).name if self.logo_path else "No logo")
        self.name.setText(rec["name"])
        self.record_id = rec["id"]
        self.update_preview()
