"""Settings page."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLineEdit,
                               QMessageBox, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from qr_studio.export import FORMATS
from qr_studio.paths import data_dir
from . import theme
from .widgets import Card, ColorButton, button, label


class SettingsPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(32, 28, 32, 28)
        v.setSpacing(16)
        v.addWidget(label("Settings", "h1"))
        s = ctx.settings

        def card(title: str):
            c = Card()
            cv = QVBoxLayout(c)
            cv.setContentsMargins(20, 18, 20, 18)
            cv.addWidget(label(title, "h2"))
            f = QFormLayout()
            cv.addLayout(f)
            v.addWidget(c)
            return f

        f = card("Saving & defaults")
        self.dl = QLineEdit(s.get("download_dir"))
        b = button("Browse")
        b.clicked.connect(lambda: self._browse(self.dl))
        r = QHBoxLayout()
        r.addWidget(self.dl, 1)
        r.addWidget(b)
        f.addRow("Default download folder", r)
        self.fmt = QComboBox()
        self.fmt.addItems(FORMATS)
        self.fmt.setCurrentText(s.get("default_format"))
        f.addRow("Default image format", self.fmt)
        self.qr_size = QSpinBox()
        self.qr_size.setRange(200, 4000)
        self.qr_size.setSingleStep(100)
        self.qr_size.setValue(int(s.get("qr_size")))
        self.qr_size.setSuffix(" px")
        f.addRow("Default QR size", self.qr_size)
        self.bw = QSpinBox()
        self.bw.setRange(1, 10)
        self.bw.setValue(int(s.get("barcode_module_width")))
        self.bh = QSpinBox()
        self.bh.setRange(40, 500)
        self.bh.setValue(int(s.get("barcode_height")))
        f.addRow("Default barcode bar width", self.bw)
        f.addRow("Default barcode height", self.bh)
        self.fg = ColorButton(s.get("fg_color"))
        self.bgc = ColorButton(s.get("bg_color"))
        f.addRow("Default foreground colour", self.fg)
        f.addRow("Default background colour", self.bgc)

        f2 = card("Scanner")
        self.suffix = QComboBox()
        self.suffix.addItems(["Enter", "Tab", "None (auto-submit after a pause)"])
        self.suffix.setCurrentIndex({"enter": 0, "tab": 1, "none": 2}.get(s.get("scanner_suffix"), 0))
        f2.addRow("Scanner sends after each scan", self.suffix)
        self.idle = QSpinBox()
        self.idle.setRange(50, 2000)
        self.idle.setSuffix(" ms")
        self.idle.setValue(int(s.get("scanner_idle_ms")))
        f2.addRow("Pause that ends a scan (suffix None)", self.idle)
        self.keep = QCheckBox("Keep the scanner input focused on the USB Scanner page")
        self.keep.setChecked(bool(s.get("scanner_keep_focus")))
        f2.addRow("", self.keep)
        self.rdir = QLineEdit(s.get("record_dir"))
        b2 = button("Browse")
        b2.clicked.connect(lambda: self._browse(self.rdir))
        r2 = QHBoxLayout()
        r2.addWidget(self.rdir, 1)
        r2.addWidget(b2)
        f2.addRow("Folder for recorded scan files", r2)

        f3 = card("Appearance")
        self.theme = QComboBox()
        self.theme.addItems(theme.theme_names())
        self.theme.setCurrentText(s.get("theme"))
        f3.addRow("Theme", self.theme)

        f4 = card("Database")
        self.dbpath = label(str(ctx.db.path), "muted", True)
        f4.addRow("Location", self.dbpath)
        bb = button("Back up database...")
        bb.clicked.connect(self.backup)
        of = button("Open data folder")
        of.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        r4 = QHBoxLayout()
        r4.addWidget(bb)
        r4.addWidget(of)
        r4.addStretch()
        f4.addRow("", r4)

        row = QHBoxLayout()
        save = button("Save settings", primary=True)
        save.clicked.connect(self.save)
        row.addWidget(save)
        row.addStretch()
        v.addLayout(row)
        v.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QScrollArea.Shape.NoFrame)
        sc.setWidget(host)
        outer.addWidget(sc)

    def _browse(self, edit: QLineEdit) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose folder", edit.text())
        if d:
            edit.setText(d)

    def save(self) -> None:
        s = self.ctx.settings
        for key, val in (("download_dir", self.dl.text().strip() or s.get("download_dir")), ("default_format", self.fmt.currentText()),
                         ("qr_size", self.qr_size.value()), ("barcode_module_width", self.bw.value()),
                         ("barcode_height", self.bh.value()), ("fg_color", self.fg.color()), ("bg_color", self.bgc.color()),
                         ("scanner_suffix", ["enter", "tab", "none"][self.suffix.currentIndex()]),
                         ("scanner_idle_ms", self.idle.value()), ("scanner_keep_focus", self.keep.isChecked()),
                         ("record_dir", self.rdir.text().strip() or s.get("record_dir")), ("theme", self.theme.currentText())):
            s.set(key, val, save=False)
        s.save()
        try:
            Path(s.get("download_dir")).mkdir(parents=True, exist_ok=True)
            Path(s.get("record_dir")).mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Settings", f"Saved, but a folder could not be created: {e}")
        theme.apply_theme(QApplication.instance(), s.get("theme"))
        self.ctx.settings_changed.emit()
        QMessageBox.information(self, "Settings", "Settings saved.")

    def backup(self) -> None:
        start = str(Path(self.ctx.settings.get("download_dir")) / f"qr_studio_backup_{datetime.now():%Y-%m-%d}.db")
        path, _ = QFileDialog.getSaveFileName(self, "Back up database", start, "SQLite database (*.db)")
        if not path:
            return
        try:
            self.ctx.db.backup(path)
        except Exception as e:
            QMessageBox.warning(self, "Backup failed", str(e))
            return
        QMessageBox.information(self, "Backup", f"Database backed up to:\n{path}")
