"""JSON-backed application settings."""
from __future__ import annotations

import json
from pathlib import Path

from .paths import data_dir, output_dir

DEFAULTS = {
    "download_dir": "",
    "default_format": "PNG",
    "qr_size": 1024,
    "barcode_module_width": 3,
    "barcode_height": 120,
    "fg_color": "#000000",
    "bg_color": "#FFFFFF",
    "scanner_suffix": "enter",      # enter | tab | none
    "scanner_idle_ms": 150,         # auto-submit pause when suffix == none
    "scanner_keep_focus": True,
    "theme": "Swiss Cream",
    "record_format": "xlsx",        # xlsx | csv
    "record_dir": "",
    "record_auto": True,
    "camera_index": 0,
    "serial_baud": 9600,
}


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else data_dir() / "settings.json"
        self.data = dict(DEFAULTS)
        self.load()
        if not self.data["download_dir"]:
            self.data["download_dir"] = str(output_dir())
        if not self.data["record_dir"]:
            self.data["record_dir"] = str(Path(self.data["download_dir"]) / "Scans")

    def load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for k in DEFAULTS:
                if k in raw and isinstance(raw[k], type(DEFAULTS[k])):
                    self.data[k] = raw[k]
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def get(self, key: str):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value, save: bool = True) -> None:
        self.data[key] = value
        if save:
            self.save()
