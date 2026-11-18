"""Bulk generation from CSV/XLSX in a background thread with progress, error report and ZIP."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox,
                               QPlainTextEdit, QProgressBar, QSpinBox, QVBoxLayout)

from qr_studio import bulk, export as ex
from qr_studio.barcode_generator import BARCODE_TYPES
from qr_studio.qr_generator import EC_LEVELS, QR_TYPES
from .widgets import button, label


class BulkWorker(QThread):
    progress = Signal(int, int)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, rows, mode, defaults, out_dir, fmt):
        super().__init__()
        self.args = (rows, mode, defaults, out_dir, fmt)
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            rows, mode, defaults, out_dir, fmt = self.args
            self.finished_ok.emit(bulk.generate_bulk(rows, mode, defaults, out_dir, fmt,
                                                     lambda i, n: self.progress.emit(i, n), lambda: self._cancel))
        except Exception as e:
            self.failed.emit(str(e))


class BulkDialog(QDialog):
    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.ctx, self.rows, self.worker, self.res = ctx, [], None, None
        self.setWindowTitle("Bulk generate")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        v.addWidget(label("Bulk generate from CSV or Excel", "h2"))
        v.addWidget(label("Columns: data (required), name and type (optional). Other QR fields such as ssid, password, first, last "
                          "are also understood. Rows that fail are reported and skipped.", "muted", True))
        f = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItems(["QR codes", "Barcodes"])
        self.default_type = QComboBox()
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        pick = button("Choose file...")
        row = QHBoxLayout()
        row.addWidget(self.file_edit, 1)
        row.addWidget(pick)
        self.out_edit = QLineEdit(str(Path(ctx.settings.get("download_dir")) / "Bulk"))
        out_pick = button("Browse")
        orow = QHBoxLayout()
        orow.addWidget(self.out_edit, 1)
        orow.addWidget(out_pick)
        self.fmt = QComboBox()
        self.fmt.addItems(["PNG", "JPG", "JPEG", "SVG", "PDF"])
        self.fmt.setCurrentText(ctx.settings.get("default_format"))
        self.size = QSpinBox()
        self.size.setRange(200, 4000)
        self.size.setValue(int(ctx.settings.get("qr_size")))
        self.save_lib = QCheckBox("Also add every code to Saved Codes")
        self.save_lib.setChecked(True)
        f.addRow("Create", self.mode)
        f.addRow("Default type", self.default_type)
        f.addRow("File", row)
        f.addRow("Output folder", orow)
        f.addRow("Image format", self.fmt)
        f.addRow("QR size", self.size)
        f.addRow("", self.save_lib)
        v.addLayout(f)
        tpl = button("Download template CSV")
        v.addWidget(tpl)
        self.bar = QProgressBar()
        v.addWidget(self.bar)
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setMinimumHeight(130)
        v.addWidget(self.report)
        btns = QHBoxLayout()
        self.go = button("Generate", primary=True)
        self.cancel_btn = button("Cancel")
        self.open_btn = button("Open output folder")
        self.open_btn.setEnabled(False)
        for b in (self.go, self.cancel_btn, self.open_btn):
            btns.addWidget(b)
        v.addLayout(btns)

        self.mode.currentIndexChanged.connect(self._mode_changed)
        pick.clicked.connect(self.pick_file)
        out_pick.clicked.connect(self.pick_out)
        tpl.clicked.connect(self.save_template)
        self.go.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(self.cancel)
        self.open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.res.zip_path.parent))))
        self._mode_changed()

    def _mode_changed(self) -> None:
        qr = self.mode.currentIndex() == 0
        self.default_type.clear()
        self.default_type.addItems(list(QR_TYPES) if qr else BARCODE_TYPES)
        self.default_type.setCurrentText("Website URL" if qr else "Code 128")
        self.size.setEnabled(qr)

    def pick_file(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Choose CSV or Excel file", "", "Data files (*.csv *.xlsx *.xlsm)")
        if not p:
            return
        try:
            self.rows = ex.read_rows(p)
        except Exception as e:
            QMessageBox.warning(self, "Bulk generate", str(e))
            return
        self.file_edit.setText(p)
        self.report.setPlainText(f"Loaded {len(self.rows)} row(s).")

    def pick_out(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Output folder", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    def save_template(self) -> None:
        p, _ = QFileDialog.getSaveFileName(self, "Save template", "bulk_template.csv", "CSV (*.csv)")
        if p:
            ex.write_template(p, "qr" if self.mode.currentIndex() == 0 else "barcode")

    def start(self) -> None:
        if not self.rows:
            QMessageBox.information(self, "Bulk generate", "Choose a CSV or Excel file with at least one row first.")
            return
        s = self.ctx.settings
        defaults = {"type": self.default_type.currentText(), "size": self.size.value(), "fg": s.get("fg_color"),
                    "bg": "#FFFFFF", "ec": EC_LEVELS["M (15%)"], "module_width": s.get("barcode_module_width"),
                    "height": s.get("barcode_height"), "show_text": True}
        self.mode_key = "qr" if self.mode.currentIndex() == 0 else "barcode"
        self.bar.setRange(0, len(self.rows))
        self.bar.setValue(0)
        self.go.setEnabled(False)
        self.worker = BulkWorker(self.rows, self.mode_key, defaults, self.out_edit.text(), self.fmt.currentText())
        self.worker.progress.connect(lambda i, n: self.bar.setValue(i))
        self.worker.finished_ok.connect(self._finished)
        self.worker.failed.connect(self.failed)
        self.worker.start()

    def cancel(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        else:
            self.reject()

    def failed(self, msg: str) -> None:
        self.go.setEnabled(True)
        self.report.setPlainText("Failed: " + msg)

    def _finished(self, res) -> None:
        self.res = res
        self.go.setEnabled(True)
        lines = [f"Created {len(res.files)} file(s)." + (" (cancelled)" if res.cancelled else "")]
        if res.zip_path:
            lines.append(f"ZIP: {res.zip_path}")
            self.open_btn.setEnabled(True)
        if res.errors:
            lines.append(f"\n{len(res.errors)} row(s) had problems:")
            lines += [f"  Row {n}: {msg}" for n, msg in res.errors]
        self.report.setPlainText("\n".join(lines))
        if self.save_lib.isChecked():
            for r in res.records:
                self.ctx.db.add_code(r["name"], r["kind"], r["code_type"], r["data"], r["options"], r["export_path"])
        if res.records:
            self.ctx.db.bump_stat("qr_generated" if self.mode_key == "qr" else "barcode_generated", len(res.records))
            self.ctx.codes_changed.emit()
