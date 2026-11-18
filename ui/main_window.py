"""Main window: sidebar navigation + pages."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from qr_studio import APP_NAME, __version__
from qr_studio.paths import resource_path
from . import context as C
from . import icons, theme
from .about_page import AboutPage
from .barcode_page import BarcodePage
from .dashboard import DashboardPage
from .history_page import HistoryPage
from .qr_page import QrPage
from .saved_codes_page import SavedCodesPage
from .scanner_page import ScannerPage
from .settings_page import SettingsPage
from .widgets import label

NAV_ICONS = ["dashboard", "qr", "barcode", "usb", "history", "saved", "settings", "info"]


class MainWindow(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1360, 840)
        self.setMinimumSize(1100, 700)
        ico = resource_path("assets/icons/app.ico")
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(248)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(16, 24, 16, 20)
        sv.setSpacing(4)
        brand = label(APP_NAME, "brand")
        sv.addWidget(brand)
        sv.addSpacing(18)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.navs: list[QPushButton] = []
        for i, name in enumerate(C.PAGES):
            b = QPushButton("  " + name)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self.go(idx))
            self.group.addButton(b, i)
            sv.addWidget(b)
            self.navs.append(b)
        sv.addStretch()
        sv.addWidget(label("Offline - your data stays on this computer", "sideNote", True))
        h.addWidget(side)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage(ctx)
        self.qr = QrPage(ctx)
        self.barcode = BarcodePage(ctx)
        self.scanner = ScannerPage(ctx)
        self.history = HistoryPage(ctx)
        self.saved = SavedCodesPage(ctx, self.reopen)
        self.settings = SettingsPage(ctx)
        self.about = AboutPage(ctx)
        for p in (self.dashboard, self.qr, self.barcode, self.scanner, self.history, self.saved, self.settings, self.about):
            self.stack.addWidget(p)
        h.addWidget(self.stack, 1)

        ctx.open_page.connect(self.go)
        ctx.settings_changed.connect(self._icons)
        self._icons()
        self.go(C.DASHBOARD)

    def _icons(self) -> None:
        p = theme.palette()
        for b, name in zip(self.navs, NAV_ICONS):
            b.setIcon(icons.icon(name, p["side_text"], "#FFFFFF", 20))

    def go(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        self.navs[idx].setChecked(True)

    def reopen(self, rec: dict) -> None:
        if rec["kind"] == "qr":
            self.qr.load_record(rec)
            self.go(C.QR)
        else:
            self.barcode.load_record(rec)
            self.go(C.BARCODE)

    def closeEvent(self, e) -> None:
        self.scanner.shutdown()
        super().closeEvent(e)
