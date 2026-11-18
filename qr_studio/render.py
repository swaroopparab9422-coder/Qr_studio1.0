"""Render a saved-code record (database row) back into an image."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from . import barcode_generator as bg
from . import qr_generator as qg


def record_options(rec: dict) -> dict:
    try:
        return json.loads(rec.get("options") or "{}")
    except ValueError:
        return {}


def render_record(rec: dict, size: int | None = None, scale: float = 1.0) -> Image.Image:
    o = record_options(rec)
    if rec["kind"] == "qr":
        logo = o.get("logo") or None
        if logo and not Path(logo).exists():
            logo = None
        return qg.make_qr_image(rec["data"], size or int(o.get("size", 1024)), o.get("fg", "#000000"),
                                o.get("bg", "#FFFFFF"), o.get("ec", "M"), logo)
    return bg.render_barcode(rec["code_type"], rec["data"], int(o.get("module_width", 3)), int(o.get("height", 120)),
                             bool(o.get("show_text", True)), o.get("fg", "#000000"), o.get("bg", "#FFFFFF"), scale)
