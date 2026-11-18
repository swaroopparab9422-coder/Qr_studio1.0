"""About Software page."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from qr_studio import APP_NAME, __version__
from qr_studio.paths import data_dir
from .widgets import Card, label


class AboutPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(32, 28, 32, 28)
        v.setSpacing(16)
        v.addWidget(label("About Software", "h1"))
        c = Card()
        cv = QVBoxLayout(c)
        cv.setContentsMargins(24, 20, 24, 20)
        cv.setSpacing(10)
        cv.addWidget(label(f"{APP_NAME}  v{__version__}", "h2"))
        cv.addWidget(label("Create QR codes and barcodes, scan them with a USB scanner or webcam, and record every scan to "
                           "CSV or Excel. Everything works offline and your data stays on this computer.", "", True))
        cv.addWidget(label("How USB scanners work", "h2"))
        cv.addWidget(label("Most USB scanners act like a keyboard: they type the code into whichever box is focused and press Enter. "
                           "QR Studio keeps its scan box focused and reads that input. Because such scanners look like an ordinary "
                           "keyboard to Windows, they cannot be identified as a separate device; the scan format (QR/EAN...) is "
                           "also not reported, so it is shown as a probable guess. Scanners with a COM/serial mode can be "
                           "connected directly from the USB Scanner page.", "", True))
        cv.addWidget(label("Your data", "h2"))
        cv.addWidget(label(f"Database, settings and default exports are stored in:\n{data_dir()}", "muted", True))
        v.addWidget(c)
        v.addStretch()
