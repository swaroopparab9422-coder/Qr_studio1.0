"""Dashboard page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget

from qr_studio import export as ex
from qr_studio import qr_generator as qg
from qr_studio import render
from . import context as C
from . import icons, theme
from .widgets import Card, ImageView, ask_image_path, button, label, make_table, set_row


class DashboardPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._preview_img = None
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        head = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(label("Dashboard", "h1"))
        col.addWidget(label("Create, scan and record every code in one place", "muted"))
        head.addLayout(col)
        head.addStretch()
        self.chip = label("Scanner ready", "chip")
        head.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)

        stats = QHBoxLayout()
        stats.setSpacing(18)
        self.nums: dict[str, object] = {}
        for key, cap in (("qr", "QR codes generated"), ("bar", "Barcodes generated"), ("today", "Scans today"), ("saved", "Saved codes")):
            c = Card()
            cv = QVBoxLayout(c)
            cv.setContentsMargins(20, 16, 20, 16)
            cv.setSpacing(2)
            cv.addWidget(label(cap, "muted"))
            n = label("0", "bigNum")
            cv.addWidget(n)
            self.nums[key] = n
            stats.addWidget(c)
        root.addLayout(stats)

        body = QHBoxLayout()
        body.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(20)
        qa = Card()
        qv = QVBoxLayout(qa)
        qv.setContentsMargins(20, 18, 20, 18)
        qv.addWidget(label("Quick actions", "h2"))
        grid = QGridLayout()
        grid.setSpacing(14)
        self.tiles = []
        for i, (icon_name, title, sub, action) in enumerate([
            ("qr", "Generate QR", "Text, URL, Wi-Fi, vCard", lambda: ctx.open_page.emit(C.QR)),
            ("barcode", "Generate barcode", "Code 128, EAN, UPC", lambda: ctx.open_page.emit(C.BARCODE)),
            ("usb", "Start scanning", "USB, webcam, record", lambda: ctx.open_page.emit(C.SCANNER)),
            ("bulk", "Bulk generate", "CSV / XLSX import", self._bulk)]):
            b = QPushButton(f"  {title}\n  {sub}")
            b.setObjectName("tile")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(74)
            b.clicked.connect(action)
            self.tiles.append((b, icon_name))
            grid.addWidget(b, 0, i)
        qv.addLayout(grid)
        left.addWidget(qa)

        rc = Card()
        rv = QVBoxLayout(rc)
        rv.setContentsMargins(20, 18, 20, 18)
        rv.addWidget(label("Recent scans", "h2"))
        self.table = make_table(["Content", "Type", "Format", "Source", "Time"], stretch=0, multi=False)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 170)
        self.table.setColumnWidth(4, 90)
        rv.addWidget(self.table)
        left.addWidget(rc, 1)
        body.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(20)
        pc = Card()
        pv = QVBoxLayout(pc)
        pv.setContentsMargins(20, 18, 20, 18)
        self.prev_title = label("Latest QR code", "h2")
        pv.addWidget(self.prev_title)
        self.preview = ImageView("")
        self.preview.setMinimumHeight(220)
        pv.addWidget(self.preview, 1)
        row = QHBoxLayout()
        self.exp = button("Export PNG", primary=True)
        self.open_btn = button("Open generator")
        row.addWidget(self.exp)
        row.addWidget(self.open_btn)
        pv.addLayout(row)
        right.addWidget(pc, 1)
        rec = Card()
        rcv = QVBoxLayout(rec)
        rcv.setContentsMargins(20, 18, 20, 18)
        rcv.addWidget(label("Scan recording", "h2"))
        self.rec_lbl = label("", "muted", True)
        rcv.addWidget(self.rec_lbl)
        go = button("Open scanner")
        go.clicked.connect(lambda: ctx.open_page.emit(C.SCANNER))
        rcv.addWidget(go)
        right.addWidget(rec)
        body.addLayout(right, 2)
        root.addLayout(body, 1)

        self.exp.clicked.connect(self.export_preview)
        self.open_btn.clicked.connect(lambda: ctx.open_page.emit(C.QR))
        ctx.scans_changed.connect(self.refresh)
        ctx.codes_changed.connect(self.refresh)
        ctx.settings_changed.connect(self.refresh)
        self.refresh()

    def _bulk(self) -> None:
        from .bulk_dialog import BulkDialog
        BulkDialog(self.ctx, self.window()).exec()

    def refresh(self) -> None:
        db = self.ctx.db
        p = theme.palette()
        self.nums["qr"].setText(f"{db.get_stat('qr_generated'):,}")
        self.nums["bar"].setText(f"{db.get_stat('barcode_generated'):,}")
        self.nums["today"].setText(f"{db.count_scans_today():,}")
        self.nums["saved"].setText(f"{int(db.scalar('SELECT COUNT(*) FROM codes')):,}")
        for b, name in self.tiles:
            b.setIcon(icons.icon(name, p["secondary"] if p["bg"] == "#F0EBD8" else p["text"], size=22))
        rows = db.search_scans(limit=6)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            set_row(self.table, i, [r["content"], r["scan_type"], r["code_format"], r["source"], (r["scanned_at"] or "")[11:16]])
        s = self.ctx.settings
        self.rec_lbl.setText(("Every scan is saved to " + ("an Excel" if s.get("record_format") == "xlsx" else "a CSV") +
                              f" file in:\n{s.get('record_dir')}") if s.get("record_auto") else "Automatic recording is off. Turn it on in USB Scanner.")
        latest = db.list_codes(kind="qr")
        try:
            if latest:
                self._preview_img = render.render_record(latest[0], size=500)
                self.prev_title.setText(f"Latest QR code - {latest[0]['name'][:30]}")
            else:
                self._preview_img = qg.make_qr_image("QR Studio", 500, p["secondary"] if p["bg"] == "#F0EBD8" else "#000000", "#FFFFFF")
                self.prev_title.setText("Sample QR code")
            self.preview.set_image(self._preview_img)
        except Exception:
            self._preview_img = None
            self.preview.clear_image("QR preview unavailable")

    def export_preview(self) -> None:
        if self._preview_img is None:
            return
        path = ask_image_path(self, self.ctx.settings, "qr_code", "Export QR code")
        if not path:
            return
        try:
            ex.save_image(self._preview_img, path)
        except Exception as e:
            QMessageBox.information(self, "Export", f"{e}\nUse the QR Code Generator page for SVG export.")
