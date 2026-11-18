"""USB Scanner page: keyboard-wedge input, live recording to CSV/Excel, serial and webcam sources."""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QImage, QKeyEvent
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
                               QLineEdit, QMessageBox, QPlainTextEdit, QScrollArea, QSpinBox, QTextEdit, QVBoxLayout, QWidget)

from qr_studio import camera_scanner, history, usb_scanner
from qr_studio.recorder import RecorderError, ScanRecorder
from qr_studio.scanner import BurstTimer, detect_type
from .widgets import Card, ImageView, button, label, make_table, set_row

SOURCE_USB = "USB Scanner (keyboard wedge)"
SOURCE_MANUAL = "Manual entry"


class ScannerLineEdit(QLineEdit):
    """Receives text typed by a keyboard-wedge scanner. Submits on Enter (always), Tab (if configured) or after a pause."""
    scanned = Signal(str, str)   # text, source label

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setObjectName("scanInput")
        self.setPlaceholderText("Scan now...")
        self.burst = BurstTimer()
        self.idle = QTimer(self)
        self.idle.setSingleShot(True)
        self.idle.timeout.connect(self.submit)

    def focusNextPrevChild(self, nxt: bool) -> bool:    # keep Tab inside the box (scanners may send Tab)
        return False

    def keyPressEvent(self, e: QKeyEvent) -> None:
        mode = self.settings.get("scanner_suffix")
        key = e.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) or (key == Qt.Key.Key_Tab and mode == "tab"):
            self.idle.stop()
            self.submit()
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return
        if e.text() and e.text().isprintable():
            self.burst.add()
        super().keyPressEvent(e)
        if mode == "none":
            self.idle.start(int(self.settings.get("scanner_idle_ms")))

    def submit(self) -> None:
        text = "".join(ch for ch in self.text() if ch.isprintable()).strip()
        source = SOURCE_USB if self.burst.looks_like_scanner() else SOURCE_MANUAL
        self.clear()
        self.burst.reset()
        if text:
            self.scanned.emit(text, source)


class CameraWorker(QThread):
    frame = Signal(QImage)
    decoded = Signal(str, str)
    failed = Signal(str)

    def __init__(self, index: int):
        super().__init__()
        self.index, self._run = index, True

    def run(self) -> None:
        try:
            import cv2
            decoder = camera_scanner.FrameDecoder()
        except ImportError:
            self.failed.emit("OpenCV is not installed (pip install opencv-python).")
            return
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW) if sys.platform.startswith("win") else cv2.VideoCapture(self.index)
        if not cap.isOpened():
            self.failed.emit(f"Could not open camera {self.index}. Is it in use by another app?")
            return
        last, n = {}, 0
        while self._run:
            ok, fr = cap.read()
            if not ok:
                self.msleep(30)
                continue
            n += 1
            if n % 3 == 0:
                for text, fmt in decoder.decode(fr):
                    now = time.monotonic()
                    if now - last.get(text, 0) > 3:
                        last[text] = now
                        self.decoded.emit(text, fmt)
            rgb = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
            h, w, _ = rgb.shape
            self.frame.emit(QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy())
            self.msleep(15)
        cap.release()

    def stop(self) -> None:
        self._run = False
        self.wait(3000)


class SerialWorker(QThread):
    line = Signal(str)
    failed = Signal(str)

    def __init__(self, port: str, baud: int):
        super().__init__()
        self.port, self.baud, self._run = port, baud, True

    def run(self) -> None:
        try:
            import serial
            ser = serial.Serial(self.port, self.baud, timeout=0.5)
        except Exception as e:
            self.failed.emit(f"Could not open {self.port}: {e}")
            return
        while self._run:
            try:
                data = ser.readline()
            except Exception as e:
                self.failed.emit(f"Serial error: {e}")
                break
            if data:
                text = data.decode("utf-8", "ignore").strip("\r\n\x00 ").strip()
                if text:
                    self.line.emit(text)
        ser.close()

    def stop(self) -> None:
        self._run = False
        self.wait(3000)


class ScannerPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.session: list[dict] = []
        self.recorder: ScanRecorder | None = None
        self.camera: CameraWorker | None = None
        self.serial: SerialWorker | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        # ================= left
        left = QVBoxLayout()
        left.setSpacing(16)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(label("USB Scanner", "h1"))
        col.addWidget(label("Scan a QR code or barcode and it is recorded automatically.", "muted"))
        head.addLayout(col)
        head.addStretch()
        self.ready_chip = label("Ready - input focused", "chip")
        head.addWidget(self.ready_chip, 0, Qt.AlignmentFlag.AlignTop)
        left.addLayout(head)

        card = Card()
        cv = QVBoxLayout(card)
        cv.setContentsMargins(20, 18, 20, 18)
        cv.setSpacing(12)
        self.input = ScannerLineEdit(ctx.settings)
        self.input.scanned.connect(lambda t, s: self.handle_scan(t, s, ""))
        cv.addWidget(self.input)
        res = QHBoxLayout()
        box = QWidget()
        box.setObjectName("resultBox")
        bv = QVBoxLayout(box)
        bv.setContentsMargins(16, 12, 16, 12)
        bv.addWidget(label("Last scan", ""))
        self.res_text = label("-", "resultText", True)
        self.res_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bv.addWidget(self.res_text)
        self.res_file = label("", "")
        bv.addWidget(self.res_file)
        res.addWidget(box, 1)
        meta = QGridLayout()
        self.m_type, self.m_fmt, self.m_time, self.m_src = (label("-", "") for _ in range(4))
        for r, (cap, w) in enumerate([("Type", self.m_type), ("Format", self.m_fmt), ("Date & time", self.m_time), ("Source", self.m_src)]):
            meta.addWidget(label(cap, "muted"), r * 2, 0)
            meta.addWidget(w, r * 2 + 1, 0)
        mw = QWidget()
        mw.setLayout(meta)
        mw.setFixedWidth(210)
        res.addWidget(mw)
        cv.addLayout(res)
        row = QHBoxLayout()
        self.copy_btn = button("Copy")
        self.clear_btn = button("Clear")
        row.addWidget(self.copy_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()
        cv.addLayout(row)
        left.addWidget(card)

        tcard = Card()
        tv = QVBoxLayout(tcard)
        tv.setContentsMargins(20, 18, 20, 18)
        self.session_title = label("This session - 0 scans", "h2")
        tv.addWidget(self.session_title)
        self.table = make_table(["#", "Date & time", "Content", "Type"], stretch=2)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(3, 150)
        tv.addWidget(self.table)
        left.addWidget(tcard, 1)
        lw = QWidget()
        lw.setLayout(left)
        root.addWidget(lw, 3)

        # ================= right
        right_host = QWidget()
        rv = QVBoxLayout(right_host)
        rv.setContentsMargins(0, 0, 6, 0)
        rv.setSpacing(16)

        rc = Card()
        r1 = QVBoxLayout(rc)
        r1.setContentsMargins(20, 18, 20, 18)
        r1.addWidget(label("Record to file", "h2"))
        self.fmt = QComboBox()
        self.fmt.addItems(["Excel (.xlsx)", "CSV (.csv)"])
        self.fmt.setCurrentIndex(0 if ctx.settings.get("record_format") == "xlsx" else 1)
        r1.addWidget(self.fmt)
        r1.addWidget(label("File name", "muted"))
        self.fname = QLineEdit()
        self.fname.setPlaceholderText(self._default_filename())
        r1.addWidget(self.fname)
        r1.addWidget(label("Folder", "muted"))
        frow = QHBoxLayout()
        self.folder = QLineEdit(ctx.settings.get("record_dir"))
        self.browse = button("Browse")
        frow.addWidget(self.folder, 1)
        frow.addWidget(self.browse)
        r1.addLayout(frow)
        self.auto = QCheckBox("Save every scan automatically")
        self.auto.setChecked(bool(ctx.settings.get("record_auto")))
        r1.addWidget(self.auto)
        self.rows_lbl = label("0 rows in file", "accentNum")
        r1.addWidget(self.rows_lbl)
        self.rec_status = label("Columns: No., Date, Time, Content, Type, Format, Source", "muted", True)
        r1.addWidget(self.rec_status)
        brow = QHBoxLayout()
        self.export_btn = button("Export now", primary=True)
        self.open_btn = button("Open folder")
        brow.addWidget(self.export_btn)
        brow.addWidget(self.open_btn)
        r1.addLayout(brow)
        rv.addWidget(rc)

        sc = Card()
        s1 = QVBoxLayout(sc)
        s1.setContentsMargins(20, 18, 20, 18)
        s1.addWidget(label("Scanner settings", "h2"))
        s1.addWidget(label("Scanner sends after each scan", "muted"))
        self.suffix = QComboBox()
        self.suffix.addItems(["Enter", "Tab", "None (auto-submit after a pause)"])
        self.suffix.setCurrentIndex({"enter": 0, "tab": 1, "none": 2}.get(ctx.settings.get("scanner_suffix"), 0))
        s1.addWidget(self.suffix)
        self.keep_focus = QCheckBox("Keep scanner input focused")
        self.keep_focus.setChecked(bool(ctx.settings.get("scanner_keep_focus")))
        s1.addWidget(self.keep_focus)
        rv.addWidget(sc)

        oc = Card()
        o1 = QVBoxLayout(oc)
        o1.setContentsMargins(20, 18, 20, 18)
        o1.addWidget(label("Other scan sources (optional)", "h2"))
        o1.addWidget(label("Serial (COM) scanner", "muted"))
        srow = QHBoxLayout()
        self.port = QComboBox()
        self.refresh_btn = button("Refresh")
        self.serial_btn = button("Connect")
        srow.addWidget(self.port, 1)
        srow.addWidget(self.refresh_btn)
        srow.addWidget(self.serial_btn)
        o1.addLayout(srow)
        self.detect_btn = button("Detect USB input devices")
        o1.addWidget(self.detect_btn)
        o1.addWidget(label("Webcam", "muted"))
        crow = QHBoxLayout()
        self.cam_index = QSpinBox()
        self.cam_index.setRange(0, 9)
        self.cam_index.setValue(int(ctx.settings.get("camera_index")))
        self.cam_btn = button("Start webcam")
        crow.addWidget(self.cam_index)
        crow.addWidget(self.cam_btn, 1)
        o1.addLayout(crow)
        self.cam_view = ImageView("")
        self.cam_view.setFixedHeight(170)
        self.cam_view.hide()
        o1.addWidget(self.cam_view)
        self.other_status = label("", "muted", True)
        o1.addWidget(self.other_status)
        rv.addWidget(oc)
        rv.addStretch()
        sc_area = QScrollArea()
        sc_area.setWidgetResizable(True)
        sc_area.setFrameShape(QScrollArea.Shape.NoFrame)
        sc_area.setWidget(right_host)
        sc_area.setMinimumWidth(380)
        sc_area.setMaximumWidth(420)
        root.addWidget(sc_area, 2)

        # ================= wiring
        self.copy_btn.clicked.connect(self.copy_result)
        self.clear_btn.clicked.connect(self.clear_result)
        self.export_btn.clicked.connect(self.export_now)
        self.open_btn.clicked.connect(self.open_folder)
        self.browse.clicked.connect(self.pick_folder)
        self.fmt.currentIndexChanged.connect(self._recording_changed)
        self.fname.editingFinished.connect(self._recording_changed)
        self.folder.editingFinished.connect(self._recording_changed)
        self.auto.toggled.connect(self._auto_changed)
        self.suffix.currentIndexChanged.connect(self._suffix_changed)
        self.keep_focus.toggled.connect(lambda v: ctx.settings.set("scanner_keep_focus", bool(v)))
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.serial_btn.clicked.connect(self.toggle_serial)
        self.detect_btn.clicked.connect(self.detect_devices)
        self.cam_btn.clicked.connect(self.toggle_camera)
        self.focus_timer = QTimer(self)
        self.focus_timer.setInterval(1000)
        self.focus_timer.timeout.connect(self._keep_focus)
        self.refresh_ports()
        self._recording_changed()

    # ---------------- helpers
    def _fmt_key(self) -> str:
        return "xlsx" if self.fmt.currentIndex() == 0 else "csv"

    def _default_filename(self) -> str:
        return f"scans_{datetime.now():%Y-%m-%d}.xlsx"

    def _chip(self, text: str) -> None:
        self.ready_chip.setText(text)

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.focus_timer.start()
        self.input.setFocus()

    def hideEvent(self, e) -> None:
        super().hideEvent(e)
        self.focus_timer.stop()
        if self.camera:
            self.toggle_camera()

    def _keep_focus(self) -> None:
        if not (self.isVisible() and self.keep_focus.isChecked()):
            return
        app = QApplication.instance()
        if app.activeModalWidget() or not self.window().isActiveWindow():
            return
        fw = app.focusWidget()
        if fw is self.input or isinstance(fw, (QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QTextEdit)):
            return
        self.input.setFocus()

    def _suffix_changed(self) -> None:
        self.ctx.settings.set("scanner_suffix", ["enter", "tab", "none"][self.suffix.currentIndex()])
        self.input.setFocus()

    # ---------------- recording
    def _recording_changed(self) -> None:
        name = self.fname.text().strip() or self._default_filename()
        fmt = self._fmt_key()
        self.fname.setPlaceholderText(f"scans_{datetime.now():%Y-%m-%d}.{fmt}")
        folder = self.folder.text().strip()
        self.ctx.settings.set("record_format", fmt, save=False)
        self.ctx.settings.set("record_dir", folder or self.ctx.settings.get("record_dir"))
        self.recorder = None
        if not self.auto.isChecked() or not folder:
            self.rows_lbl.setText("Recording is off" if not self.auto.isChecked() else "Choose a folder")
            return
        try:
            self.recorder = ScanRecorder(folder, fmt, self.fname.text().strip() or None)
            self.rows_lbl.setText(f"{self.recorder.rows_in_file} rows in file")
            self.rec_status.setText(f"Saving to: {self.recorder.path.name}")
        except (RecorderError, OSError, ValueError) as e:
            self.rows_lbl.setText("Cannot record")
            self.rec_status.setText(str(e))

    def _auto_changed(self, on: bool) -> None:
        self.ctx.settings.set("record_auto", bool(on))
        self._recording_changed()

    def pick_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Folder for scan files", self.folder.text())
        if d:
            self.folder.setText(d)
            self._recording_changed()

    def open_folder(self) -> None:
        p = Path(self.folder.text().strip() or self.ctx.settings.get("record_dir"))
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def export_now(self) -> None:
        if not self.session:
            QMessageBox.information(self, "QR Studio", "No scans in this session yet. Use Scan History to export older scans.")
            return
        default = Path(self.folder.text().strip() or self.ctx.settings.get("record_dir")) / f"session_{datetime.now():%Y-%m-%d_%H%M%S}.{self._fmt_key()}"
        path, _ = QFileDialog.getSaveFileName(self, "Export this session", str(default), "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        rows = [[i, s["date"], s["time"], s["content"], s["type"], s["format"], s["source"]] for i, s in enumerate(self.session, 1)]
        try:
            (history.write_xlsx if path.lower().endswith(".xlsx") else history.write_csv)(path, history.HEADERS, rows)
        except PermissionError:
            QMessageBox.warning(self, "Export failed", "The file is open in another program. Close it and try again.")
            return
        except Exception as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self.rec_status.setText(f"Exported {len(rows)} scans to {Path(path).name}")

    # ---------------- scanning
    def handle_scan(self, text: str, source: str, fmt_hint: str) -> None:
        dtype, guess = detect_type(text)
        fmt = fmt_hint or guess or "Not reported (keyboard-wedge)"
        self.ctx.db.add_scan(text, dtype, fmt, source)
        now = datetime.now()
        entry = {"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M:%S"), "content": text, "type": dtype,
                 "format": fmt, "source": source}
        self.session.append(entry)
        self.res_text.setText(text)
        self.m_type.setText(dtype)
        self.m_fmt.setText(fmt)
        self.m_time.setText(now.strftime("%d %b %Y, %H:%M:%S"))
        self.m_src.setText(source)
        row = self.table.rowCount()
        self.table.insertRow(row)
        set_row(self.table, row, [len(self.session), f"{entry['date']} {entry['time']}", text, dtype])
        self.table.scrollToBottom()
        self.session_title.setText(f"This session - {len(self.session)} scans")
        self.res_file.setText("")
        if self.recorder is not None:
            try:
                self.recorder.add(text, dtype, fmt, source, now)
                self.rows_lbl.setText(f"{self.recorder.rows_in_file} rows in file")
                self.res_file.setText(f"Saved to {self.recorder.path.name}")
                self._chip("Ready - input focused")
            except RecorderError as e:
                self.rec_status.setText(str(e))
                self._chip("File locked - scans are queued")
                self.res_file.setText("Saved to history; file write pending")
        self.ctx.scans_changed.emit()
        self.input.setFocus()

    def copy_result(self) -> None:
        if self.session:
            QApplication.clipboard().setText(self.session[-1]["content"])
            self._chip("Copied")
            QTimer.singleShot(1500, lambda: self._chip("Ready - input focused"))

    def clear_result(self) -> None:
        self.input.clear()
        self.res_text.setText("-")
        for w in (self.m_type, self.m_fmt, self.m_time, self.m_src):
            w.setText("-")
        self.res_file.setText("")
        self.input.setFocus()

    # ---------------- serial / devices / webcam
    def refresh_ports(self) -> None:
        self.port.clear()
        ports = usb_scanner.list_serial_ports()
        for dev, desc in ports:
            self.port.addItem(f"{dev} - {desc}", dev)
        if not usb_scanner.serial_available():
            self.other_status.setText("Serial support needs the 'pyserial' package.")
        elif not ports:
            self.port.addItem("No COM ports found")

    def toggle_serial(self) -> None:
        if self.serial:
            self.serial.stop()
            self.serial = None
            self.serial_btn.setText("Connect")
            self.other_status.setText("Serial scanner disconnected.")
            return
        dev = self.port.currentData()
        if not dev:
            self.other_status.setText("Select a COM port first.")
            return
        self.serial = SerialWorker(dev, int(self.ctx.settings.get("serial_baud")))
        self.serial.line.connect(lambda t, d=dev: self.handle_scan(t, f"Serial {d}", ""))
        self.serial.failed.connect(self._serial_failed)
        self.serial.start()
        self.serial_btn.setText("Disconnect")
        self.other_status.setText(f"Listening on {dev}...")

    def _serial_failed(self, msg: str) -> None:
        self.other_status.setText(msg)
        if self.serial:
            self.serial = None
        self.serial_btn.setText("Connect")

    def detect_devices(self) -> None:
        names = usb_scanner.list_hid_devices()
        note = ("Scanners in keyboard mode usually appear as a generic 'HID Keyboard Device' and cannot be told apart from "
                "your keyboard - that is normal. Click the scan box and scan a code to test it.")
        if not names:
            QMessageBox.information(self, "USB input devices", "No devices could be listed (this works on Windows only).\n\n" + note)
        else:
            QMessageBox.information(self, "USB input devices", "\n".join(names) + "\n\n" + note)

    def toggle_camera(self) -> None:
        if self.camera:
            self.camera.stop()
            self.camera = None
            self.cam_btn.setText("Start webcam")
            self.cam_view.hide()
            return
        if not camera_scanner.opencv_available():
            self.other_status.setText("Webcam scanning needs OpenCV (pip install opencv-python).")
            return
        self.ctx.settings.set("camera_index", self.cam_index.value())
        self.camera = CameraWorker(self.cam_index.value())
        self.camera.frame.connect(self.cam_view.set_qimage)
        self.camera.decoded.connect(lambda t, f: self.handle_scan(t, "Webcam", f))
        self.camera.failed.connect(self._camera_failed)
        self.camera.start()
        self.cam_view.show()
        self.cam_btn.setText("Stop webcam")

    def _camera_failed(self, msg: str) -> None:
        self.other_status.setText(msg)
        self.camera = None
        self.cam_btn.setText("Start webcam")
        self.cam_view.hide()

    def shutdown(self) -> None:
        if self.camera:
            self.camera.stop()
        if self.serial:
            self.serial.stop()
