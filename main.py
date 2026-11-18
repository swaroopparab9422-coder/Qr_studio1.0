"""QR Studio entry point."""
from __future__ import annotations

import logging
import sys
import traceback

from qr_studio import APP_NAME
from qr_studio.paths import data_dir, ensure_dirs, resource_path


def main() -> int:
    ensure_dirs()
    logging.basicConfig(filename=str(data_dir() / "qr_studio.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    from PySide6.QtGui import QFont, QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QRStudio.App")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Segoe UI", 10))
    ico = resource_path("assets/icons/app.ico")
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))

    def hook(exc_type, exc, tb):
        logging.error("Unhandled error:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))
        try:
            QMessageBox.critical(None, APP_NAME, f"Something went wrong:\n{exc}\n\nDetails were saved to qr_studio.log in:\n{data_dir()}")
        except Exception:
            pass

    sys.excepthook = hook

    from qr_studio.database import Database
    from qr_studio.settings import Settings
    from ui import theme
    from ui.context import AppContext
    from ui.main_window import MainWindow

    settings = Settings()
    db = Database()
    theme.apply_theme(app, settings.get("theme"))
    ctx = AppContext(db, settings)
    win = MainWindow(ctx)
    win.show()
    code = app.exec()
    db.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
