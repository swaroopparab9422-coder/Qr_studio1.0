"""Saving images (PNG/JPG/JPEG/SVG/PDF), ZIP batches and reading CSV/XLSX input files."""
from __future__ import annotations

import csv
import re
import zipfile
from pathlib import Path

from PIL import Image

from . import barcode_generator as bg
from . import qr_generator as qg

FORMATS = ["PNG", "JPG", "JPEG", "SVG", "PDF"]
FILTERS = {"PNG": "PNG image (*.png)", "JPG": "JPG image (*.jpg)", "JPEG": "JPEG image (*.jpeg)",
           "SVG": "SVG vector (*.svg)", "PDF": "PDF for printing (*.pdf)"}


def safe_filename(name: str, default: str = "code") -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (name or "").strip()).strip(" .")
    return name[:120] or default


def unique_path(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        return path
    for i in range(1, 10000):
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not cand.exists():
            return cand
    return path


def save_image(img: Image.Image, path: str | Path, dpi: int = 300) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()
    rgb = img.convert("RGB")
    if ext in (".jpg", ".jpeg"):
        rgb.save(path, "JPEG", quality=95, subsampling=0, dpi=(dpi, dpi))
    elif ext == ".pdf":
        rgb.save(path, "PDF", resolution=float(dpi))
    elif ext == ".png":
        rgb.save(path, "PNG", dpi=(dpi, dpi))
    else:
        raise ValueError(f"Unsupported image format: {ext}")
    return path


def export_qr(data: str, path: str | Path, size: int, fg: str, bg_color: str, ec: str, logo: str | None) -> Path:
    path = Path(path)
    if path.suffix.lower() == ".svg":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(qg.make_qr_svg(data, fg, bg_color, ec, logo), encoding="utf-8")
        return path
    img = qg.make_qr_image(data, size, fg, bg_color, ec, logo)
    return save_image(img, path, dpi=300)


def export_barcode(kind: str, data: str, path: str | Path, module_width: int, height: int, show_text: bool,
                   fg: str, bg_color: str, scale: float = 3.0) -> Path:
    path = Path(path)
    if path.suffix.lower() == ".svg":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(bg.render_barcode_svg(kind, data, module_width, height, show_text, fg, bg_color), encoding="utf-8")
        return path
    img = bg.render_barcode(kind, data, module_width, height, show_text, fg, bg_color, scale=scale)
    return save_image(img, path, dpi=300)


def make_zip(files: list[Path], zip_path: str | Path) -> Path:
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, Path(f).name)
    return zip_path


# ------------------------------------------------------------------ input files
_DATA_ALIASES = ("data", "content", "value", "text", "url", "code", "barcode", "qr")
_NAME_ALIASES = ("name", "filename", "file", "label", "title")


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def read_rows(path: str | Path) -> list[dict]:
    """Read a CSV/XLSX file into dicts with lower-case keys. A header row is optional:
    without one, column 1 is the data and column 2 the optional name."""
    path = Path(path)
    ext = path.suffix.lower()
    raw: list[list[str]] = []
    if ext in (".csv", ".txt"):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        raw = [[_cell(c) for c in row] for row in csv.reader(text.splitlines(), dialect)]
    elif ext in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Excel files need the 'openpyxl' package (pip install openpyxl).") from exc
        wb = load_workbook(str(path), read_only=True, data_only=True)
        try:
            raw = [[_cell(c) for c in row] for row in wb.worksheets[0].iter_rows(values_only=True)]
        finally:
            wb.close()
    else:
        raise ValueError("Please choose a .csv or .xlsx file.")
    raw = [r for r in raw if any(c for c in r)]
    if not raw:
        return []
    head = [c.lower() for c in raw[0]]
    known = set(_DATA_ALIASES) | set(_NAME_ALIASES) | {"type", "ssid", "password", "security", "first", "last"}
    if any(h in known for h in head):
        rows = []
        for line_no, r in enumerate(raw[1:], start=2):
            d = {head[i]: (r[i] if i < len(r) else "") for i in range(len(head)) if head[i]}
            d["_row"] = line_no
            data = next((d[a] for a in _DATA_ALIASES if d.get(a)), "")
            d["data"] = data
            d["name"] = next((d[a] for a in _NAME_ALIASES if d.get(a)), "")
            rows.append(d)
        return rows
    return [{"data": r[0], "name": r[1] if len(r) > 1 else "", "_row": i} for i, r in enumerate(raw, start=1)]


def write_template(path: str | Path, mode: str) -> Path:
    path = Path(path)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if mode == "qr":
            w.writerow(["name", "type", "data"])
            w.writerows([["Website", "Website URL", "https://example.com"], ["Phone", "Phone Number", "+919876543210"],
                         ["Note", "Plain Text", "Hello from QR Studio"]])
        else:
            w.writerow(["name", "type", "data"])
            w.writerows([["Product A", "Code 128", "SKU-0001"], ["Product B", "EAN-13", "890123456789"],
                         ["Box label", "Code 39", "BOX-123"]])
    return path
