"""Bulk generation from CSV/XLSX rows. Pure Python (no Qt) so it can run in a background thread."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import export as ex
from . import qr_generator as qg
from .barcode_generator import BARCODE_TYPES

_QR_ALIASES = {"text": "Plain Text", "plaintext": "Plain Text", "url": "Website URL", "website": "Website URL",
               "websiteurl": "Website URL", "pdf": "PDF URL", "pdfurl": "PDF URL", "email": "Email Address",
               "emailaddress": "Email Address", "phone": "Phone Number", "phonenumber": "Phone Number",
               "whatsapp": "WhatsApp", "wifi": "Wi-Fi Network", "wifinetwork": "Wi-Fi Network",
               "vcard": "Contact Details / vCard", "contact": "Contact Details / vCard", "sms": "SMS",
               "maps": "Google Maps Location", "googlemaps": "Google Maps Location", "location": "Google Maps Location",
               "instagram": "Instagram", "facebook": "Facebook", "youtube": "YouTube", "linkedin": "LinkedIn",
               "custom": "Custom URL", "customurl": "Custom URL"}
_PRIMARY = {"Plain Text": "text", "Website URL": "url", "PDF URL": "url", "Custom URL": "url", "Email Address": "address",
            "Phone Number": "number", "WhatsApp": "number", "SMS": "number", "Wi-Fi Network": "ssid",
            "Google Maps Location": "location", "Instagram": "username", "Facebook": "page", "YouTube": "channel",
            "LinkedIn": "profile", "Contact Details / vCard": "first"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def match_qr_type(name: str, default: str) -> str:
    if not name:
        return default
    n = _norm(name)
    for t in qg.QR_TYPES:
        if _norm(t) == n:
            return t
    if n in _QR_ALIASES:
        return _QR_ALIASES[n]
    raise ValueError(f"Unknown QR type '{name}'")


def match_barcode_type(name: str, default: str) -> str:
    if not name:
        return default
    for t in BARCODE_TYPES:
        if _norm(t) == _norm(name):
            return t
    raise ValueError(f"Unknown barcode type '{name}'")


@dataclass
class BulkResult:
    files: list[Path] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)   # (row number, reason)
    records: list[dict] = field(default_factory=list)             # ready for Database.add_code
    zip_path: Path | None = None
    cancelled: bool = False


def generate_bulk(rows: list[dict], mode: str, defaults: dict, out_dir: str | Path, fmt: str = "PNG",
                  progress: Callable[[int, int], None] | None = None,
                  cancelled: Callable[[], bool] | None = None) -> BulkResult:
    """mode: 'qr' or 'barcode'. defaults: type, size, fg, bg, ec, module_width, height, show_text."""
    res = BulkResult()
    out = Path(out_dir) / f"batch_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    ext = "." + fmt.lower()
    total = len(rows)
    for i, row in enumerate(rows, start=1):
        if cancelled and cancelled():
            res.cancelled = True
            break
        rn = row.get("_row", i)
        try:
            if not (row.get("data") or "").strip() and mode == "barcode":
                raise ValueError("Empty data")
            if mode == "qr":
                qtype = match_qr_type(row.get("type", ""), defaults["type"])
                values = {f.key: row[f.key] for f in qg.QR_TYPES[qtype] if row.get(f.key)}
                prim = _PRIMARY.get(qtype)
                if prim and prim not in values and row.get("data"):
                    values[prim] = row["data"]
                payload = qg.build_payload(qtype, values)
                label = row.get("name") or row.get("data") or qtype
                path = ex.unique_path(out / f"{i:03d}_{ex.safe_filename(label)[:50]}{ext}")
                ex.export_qr(payload, path, int(defaults["size"]), defaults["fg"], defaults["bg"], defaults["ec"], None)
                opts = {"qr_type": qtype, "fields": values, "size": int(defaults["size"]), "fg": defaults["fg"],
                        "bg": defaults["bg"], "ec": defaults["ec"], "logo": ""}
                res.records.append({"name": label[:80], "kind": "qr", "code_type": qtype, "data": payload,
                                    "options": json.dumps(opts), "export_path": str(path)})
            else:
                btype = match_barcode_type(row.get("type", ""), defaults["type"])
                label = row.get("name") or row["data"]
                path = ex.unique_path(out / f"{i:03d}_{ex.safe_filename(label)[:50]}{ext}")
                ex.export_barcode(btype, row["data"], path, int(defaults["module_width"]), int(defaults["height"]),
                                  bool(defaults.get("show_text", True)), defaults["fg"], defaults["bg"], scale=3.0)
                from .barcode_generator import validate
                clean = validate(btype, row["data"])
                opts = {"module_width": int(defaults["module_width"]), "height": int(defaults["height"]),
                        "show_text": bool(defaults.get("show_text", True)), "fg": defaults["fg"], "bg": defaults["bg"]}
                res.records.append({"name": label[:80], "kind": "barcode", "code_type": btype, "data": clean,
                                    "options": json.dumps(opts), "export_path": str(path)})
            res.files.append(path)
        except Exception as exc:  # report and continue with the next row
            res.errors.append((rn, str(exc)))
        if progress:
            progress(i, total)
    if res.files:
        res.zip_path = ex.make_zip(res.files, out / f"{out.name}.zip")
    return res
