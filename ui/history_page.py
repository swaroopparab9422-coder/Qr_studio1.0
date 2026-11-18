"""Scan History page: search, filter, copy, delete, clear, export CSV/Excel."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLineEdit, QMessageBox, QVBoxLayout, QWidget)

from qr_studio import history
from .widgets import Card, button, label, make_table, selected_ids, set_row

SOURCES = ["All sources", "USB Scanner", "Webcam", "Serial", "Manual entry"]


class HistoryPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.rows: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)
        root.addWidget(label("Scan History", "h1"))
        root.addWidget(label("Every scan is stored on this computer. Search, filter and export it.", "muted"))
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 18, 20, 18)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search content, type, date...")
        self.type_f = QComboBox()
        self.src_f = QComboBox()
        self.src_f.addItems(SOURCES)
        for w in (self.search, self.type_f, self.src_f):
            bar.addWidget(w, 3 if w is self.search else 1)
        v.addLayout(bar)
        self.table = make_table(["ID", "Date & time", "Content", "Type", "Format", "Source"], stretch=2)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 150)
        self.table.setColumnWidth(5, 190)
        v.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.count = label("", "muted")
        self.copy_btn = button("Copy selected")
        self.del_btn = button("Delete selected", danger=True)
        self.clear_btn = button("Clear history", danger=True)
        self.csv_btn = button("Export CSV", primary=True)
        self.xlsx_btn = button("Export Excel", primary=True)
        row.addWidget(self.count)
        row.addStretch()
        for b in (self.copy_btn, self.del_btn, self.clear_btn, self.csv_btn, self.xlsx_btn):
            row.addWidget(b)
        v.addLayout(row)
        root.addWidget(card, 1)

        self.search.textChanged.connect(self.reload)
        self.type_f.currentIndexChanged.connect(self.reload)
        self.src_f.currentIndexChanged.connect(self.reload)
        self.copy_btn.clicked.connect(self.copy_selected)
        self.del_btn.clicked.connect(self.delete_selected)
        self.clear_btn.clicked.connect(self.clear_all)
        self.csv_btn.clicked.connect(lambda: self.export("csv"))
        self.xlsx_btn.clicked.connect(lambda: self.export("xlsx"))
        ctx.scans_changed.connect(self.reload)
        self.reload()

    def _refresh_types(self) -> None:
        cur = self.type_f.currentText()
        self.type_f.blockSignals(True)
        self.type_f.clear()
        self.type_f.addItem("All types")
        self.type_f.addItems(self.ctx.db.scan_types())
        i = self.type_f.findText(cur)
        self.type_f.setCurrentIndex(max(0, i))
        self.type_f.blockSignals(False)

    def reload(self) -> None:
        self._refresh_types()
        t = self.type_f.currentText()
        s = self.src_f.currentText()
        self.rows = self.ctx.db.search_scans(self.search.text().strip(), "" if t == "All types" else t,
                                             "" if s == "All sources" else s)
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            set_row(self.table, i, [r["id"], r["scanned_at"], r["content"], r["scan_type"], r["code_format"], r["source"]], data=r["id"])
        self.count.setText(f"{len(self.rows)} scans")

    def copy_selected(self) -> None:
        ids = set(selected_ids(self.table))
        text = "\n".join(r["content"] for r in self.rows if r["id"] in ids)
        if text:
            QApplication.clipboard().setText(text)

    def delete_selected(self) -> None:
        ids = selected_ids(self.table)
        if not ids:
            return
        if QMessageBox.question(self, "Delete scans", f"Delete {len(ids)} selected scan(s)?") == QMessageBox.StandardButton.Yes:
            self.ctx.db.delete_scans(ids)
            self.ctx.scans_changed.emit()

    def clear_all(self) -> None:
        if not self.ctx.db.scalar("SELECT COUNT(*) FROM scans"):
            return
        if QMessageBox.question(self, "Clear history", "Delete ALL scan history? This cannot be undone.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Yes:
            self.ctx.db.clear_scans()
            self.ctx.scans_changed.emit()

    def export(self, fmt: str) -> None:
        if not self.rows:
            QMessageBox.information(self, "QR Studio", "There are no scans to export.")
            return
        start = str(Path(self.ctx.settings.get("record_dir")) / f"scan_history_{datetime.now():%Y-%m-%d}.{fmt}")
        path, _ = QFileDialog.getSaveFileName(self, "Export scan history", start,
                                              "Excel (*.xlsx)" if fmt == "xlsx" else "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith("." + fmt):
            path += "." + fmt
        try:
            history.export_scans(list(reversed(self.rows)), path)
        except PermissionError:
            QMessageBox.warning(self, "Export failed", "The file is open in another program. Close it and try again.")
            return
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        QMessageBox.information(self, "Exported", f"Saved {len(self.rows)} scans to:\n{path}")
