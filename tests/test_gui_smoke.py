import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_main_window_builds_and_scan_is_recorded(tmp_path):
    pytest.importorskip("qrcode")
    from PySide6.QtWidgets import QApplication

    from qr_studio.database import Database
    from qr_studio.settings import Settings
    from ui import theme
    from ui.context import AppContext
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    st = Settings(tmp_path / "s.json")
    st.set("record_dir", str(tmp_path / "scans"), save=False)
    st.set("download_dir", str(tmp_path), save=False)
    db = Database(tmp_path / "t.db")
    theme.apply_theme(app, "Swiss Cream")
    win = MainWindow(AppContext(db, st))
    win.show()
    for i in range(8):
        win.go(i)
        app.processEvents()
        assert not win.grab().isNull()
    win.scanner.handle_scan("8901234567890", "USB Scanner (keyboard wedge)", "")
    assert db.count_scans_today() == 1
    assert win.scanner.recorder is not None and win.scanner.recorder.rows_in_file == 1
    win.scanner.shutdown()
