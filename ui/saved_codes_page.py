"""Saved Codes page: browse, reopen, export again, delete, print sheets, bulk generation."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QMessageBox, QVBoxLayout, QWidget

from qr_studio import export as ex
from qr_studio import render
from .widgets import Card, ImageView, ask_image_path, button, label, make_table, selected_ids, set_row


class SavedCodesPage(QWidget):
    def __init__(self, ctx, on_reopen):
        super().__init__()
        self.ctx, self.on_reopen = ctx, on_reopen
        self.rows: list[dict] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(label("Saved Codes", "h1"))
        col.addWidget(label("Every QR code and barcode you saved or exported.", "muted"))
        head.addLayout(col)
        head.addStretch()
        self.bulk_btn = button("Bulk generate...")
        self.print_btn = button("Print sheet...")
        head.addWidget(self.bulk_btn)
        head.addWidget(self.print_btn)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(20)
        card = Card()
        v = QVBoxLayout(card)
        v.setContentsMargins(20, 18, 20, 18)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by name, type or content...")
        self.kind = QComboBox()
        self.kind.addItems(["All codes", "QR codes", "Barcodes"])
        bar.addWidget(self.search, 3)
        bar.addWidget(self.kind, 1)
        v.addLayout(bar)
        self.table = make_table(["ID", "Name", "Kind", "Type", "Created"], stretch=1)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 170)
        self.table.setColumnWidth(4, 150)
        v.addWidget(self.table, 1)
        self.count = label("", "muted")
        v.addWidget(self.count)
        body.addWidget(card, 3)

        pc = Card()
        pv = QVBoxLayout(pc)
        pv.setContentsMargins(20, 18, 20, 18)
        pv.addWidget(label("Preview", "h2"))
        self.preview = ImageView("Select a code")
        pv.addWidget(self.preview, 1)
        self.info = label("", "muted", True)
        pv.addWidget(self.info)
        row = QHBoxLayout()
        self.open_btn = button("Reopen", primary=True)
        self.export_btn = button("Export again")
        self.del_btn = button("Delete", danger=True)
        for b in (self.open_btn, self.export_btn, self.del_btn):
            row.addWidget(b)
        pv.addLayout(row)
        pc.setMinimumWidth(340)
        pc.setMaximumWidth(400)
        body.addWidget(pc, 2)
        root.addLayout(body, 1)

        self.search.textChanged.connect(self.reload)
        self.kind.currentIndexChanged.connect(self.reload)
        self.table.itemSelectionChanged.connect(self.show_preview)
        self.table.itemDoubleClicked.connect(lambda *_: self.reopen())
        self.open_btn.clicked.connect(self.reopen)
        self.export_btn.clicked.connect(self.export_again)
        self.del_btn.clicked.connect(self.delete)
        self.print_btn.clicked.connect(self.print_sheet)
        self.bulk_btn.clicked.connect(self.bulk)
        ctx.codes_changed.connect(self.reload)
        self.reload()

    def reload(self) -> None:
        kind = {0: "", 1: "qr", 2: "barcode"}[self.kind.currentIndex()]
        self.rows = self.ctx.db.list_codes(self.search.text().strip(), kind)
        self.table.setRowCount(len(self.rows))
        for i, r in enumerate(self.rows):
            set_row(self.table, i, [r["id"], r["name"], "QR" if r["kind"] == "qr" else "Barcode", r["code_type"], r["created_at"]], data=r["id"])
        self.count.setText(f"{len(self.rows)} codes")
        self.show_preview()

    def _selected(self) -> list[dict]:
        ids = set(selected_ids(self.table))
        return [r for r in self.rows if r["id"] in ids]

    def show_preview(self) -> None:
        sel = self._selected()
        if not sel:
            self.preview.clear_image("Select a code")
            self.info.setText("")
            return
        r = sel[0]
        try:
            self.preview.set_image(render.render_record(r, size=500))
        except Exception as e:
            self.preview.clear_image("Could not draw this code")
            self.info.setText(str(e))
            return
        self.info.setText(f"{r['data'][:200]}\n" + (f"Last export: {r['export_path']}" if r.get("export_path") else "Not exported yet"))

    def reopen(self) -> None:
        sel = self._selected()
        if sel:
            self.on_reopen(sel[0])

    def export_again(self) -> None:
        sel = self._selected()
        if not sel:
            QMessageBox.information(self, "QR Studio", "Select a code first.")
            return
        r = sel[0]
        path = ask_image_path(self, self.ctx.settings, ex.safe_filename(r["name"]), "Export code")
        if not path:
            return
        try:
            o = render.record_options(r)
            if r["kind"] == "qr":
                logo = o.get("logo") or None
                ex.export_qr(r["data"], path, int(o.get("size", 1024)), o.get("fg", "#000000"), o.get("bg", "#FFFFFF"), o.get("ec", "M"), logo)
            else:
                ex.export_barcode(r["code_type"], r["data"], path, int(o.get("module_width", 3)), int(o.get("height", 120)),
                                  bool(o.get("show_text", True)), o.get("fg", "#000000"), o.get("bg", "#FFFFFF"), 3.0)
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self.ctx.db.update_code_export(r["id"], str(path))
        self.ctx.codes_changed.emit()
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")

    def delete(self) -> None:
        ids = selected_ids(self.table)
        if ids and QMessageBox.question(self, "Delete", f"Delete {len(ids)} saved code(s)?") == QMessageBox.StandardButton.Yes:
            self.ctx.db.delete_codes(ids)
            self.ctx.codes_changed.emit()

    def print_sheet(self) -> None:
        from .print_dialog import PrintDialog
        items = self._selected() or self.rows
        if not items:
            QMessageBox.information(self, "QR Studio", "There are no saved codes to print.")
            return
        PrintDialog(items, self.window()).exec()

    def bulk(self) -> None:
        from .bulk_dialog import BulkDialog
        BulkDialog(self.ctx, self.window()).exec()
