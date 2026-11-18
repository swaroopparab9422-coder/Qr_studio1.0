"""Print layout: several codes per A4 page, preview, PDF export and direct Windows printing."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPageSize, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import (QCheckBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QMessageBox,
                               QSpinBox, QVBoxLayout)

from qr_studio import printing, render
from .widgets import button, label, pil_to_qimage


class PrintDialog(QDialog):
    def __init__(self, records: list[dict], parent=None):
        super().__init__(parent)
        self.records = records
        self.setWindowTitle("Print sheet")
        self.setMinimumWidth(420)
        v = QVBoxLayout(self)
        v.addWidget(label(f"{len(records)} code(s) selected", "h2"))
        f = QFormLayout()
        self.rows = QSpinBox()
        self.rows.setRange(1, 20)
        self.rows.setValue(4)
        self.cols = QSpinBox()
        self.cols.setRange(1, 10)
        self.cols.setValue(3)
        self.margin = QDoubleSpinBox()
        self.margin.setRange(0, 40)
        self.margin.setValue(10)
        self.margin.setSuffix(" mm")
        self.caps = QCheckBox("Print names under codes")
        self.caps.setChecked(True)
        f.addRow("Rows per page", self.rows)
        f.addRow("Columns per page", self.cols)
        f.addRow("Page margin", self.margin)
        f.addRow("", self.caps)
        v.addLayout(f)
        v.addWidget(label("Page size: A4", "muted"))
        row = QHBoxLayout()
        self.prev_btn = button("Print preview")
        self.pdf_btn = button("Save as PDF")
        self.print_btn = button("Print...", primary=True)
        for b in (self.prev_btn, self.pdf_btn, self.print_btn):
            row.addWidget(b)
        v.addLayout(row)
        self.prev_btn.clicked.connect(self.preview)
        self.pdf_btn.clicked.connect(self.save_pdf)
        self.print_btn.clicked.connect(self.print_now)

    def pages(self):
        items = []
        for r in self.records:
            try:
                items.append((render.render_record(r, size=700, scale=2.0), r["name"]))
            except Exception:
                continue
        return printing.build_sheets(items, self.rows.value(), self.cols.value(), self.margin.value(), captions=self.caps.isChecked())

    def _safe_pages(self):
        try:
            return self.pages()
        except Exception as e:
            QMessageBox.warning(self, "Print sheet", str(e))
            return None

    def save_pdf(self) -> None:
        pages = self._safe_pages()
        if not pages:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save print sheet", "print_sheet.pdf", "PDF (*.pdf)")
        if path:
            try:
                printing.save_pdf(pages, path if path.lower().endswith(".pdf") else path + ".pdf")
                QMessageBox.information(self, "Print sheet", f"Saved {len(pages)} page(s).")
            except Exception as e:
                QMessageBox.warning(self, "Print sheet", str(e))

    @staticmethod
    def _paint(printer: QPrinter, pages) -> None:
        painter = QPainter(printer)
        for i, pg in enumerate(pages):
            if i:
                printer.newPage()
            rect = printer.pageLayout().paintRectPixels(printer.resolution())
            qimg = pil_to_qimage(pg)
            scaled = qimg.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(QRect(0, 0, scaled.width(), scaled.height()), scaled)
        painter.end()

    def _printer(self) -> QPrinter:
        p = QPrinter(QPrinter.PrinterMode.HighResolution)
        p.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        return p

    def preview(self) -> None:
        pages = self._safe_pages()
        if pages:
            dlg = QPrintPreviewDialog(self._printer(), self)
            dlg.paintRequested.connect(lambda pr: self._paint(pr, pages))
            dlg.exec()

    def print_now(self) -> None:
        pages = self._safe_pages()
        if not pages:
            return
        printer = self._printer()
        if QPrintDialog(printer, self).exec() == QDialog.DialogCode.Accepted:
            self._paint(printer, pages)
