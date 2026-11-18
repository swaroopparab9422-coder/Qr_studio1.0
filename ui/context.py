"""Shared application state passed to every page."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

PAGES = ["Dashboard", "QR Code Generator", "Barcode Generator", "USB Scanner", "Scan History", "Saved Codes",
         "Settings", "About Software"]
(DASHBOARD, QR, BARCODE, SCANNER, HISTORY, SAVED, SETTINGS, ABOUT) = range(8)


class AppContext(QObject):
    scans_changed = Signal()
    codes_changed = Signal()
    settings_changed = Signal()
    open_page = Signal(int)

    def __init__(self, db, settings):
        super().__init__()
        self.db = db
        self.settings = settings
