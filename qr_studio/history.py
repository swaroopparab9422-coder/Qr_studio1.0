"""Exporting scan history / sessions to CSV or Excel (formula-injection safe)."""
from __future__ import annotations

import csv
from pathlib import Path

HEADERS = ["No.", "Date", "Time", "Content", "Type", "Format", "Source"]
FULL_HEADERS = ["ID", "Date", "Time", "Content", "Type", "Format", "Source", "Generated code details", "Export file location"]


def safe_cell(v):
    """Stop spreadsheet apps from running scanned text as a formula (CSV/Excel injection)."""
    if isinstance(v, str) and v and v[0] in "=+-@\t\r":
        return "'" + v
    return v


def scan_row(r: dict) -> list:
    date, _, time_ = (r.get("scanned_at") or "").partition(" ")
    return [r["id"], date, time_, r["content"], r.get("scan_type") or "", r.get("code_format") or "",
            r.get("source") or "", r.get("generated_details") or "", r.get("export_path") or ""]


def write_csv(path: str | Path, headers: list[str], rows: list[list]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows([[safe_cell(c) for c in row] for row in rows])
    return path


def write_xlsx(path: str | Path, headers: list[str], rows: list[list], sheet: str = "Scans") -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Excel export needs the 'openpyxl' package (pip install openpyxl).") from exc
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(headers)
    for c in ws[1]:
        c.font = Font(bold=True)
    for row in rows:
        ws.append([safe_cell(c) for c in row])
    for col, width in zip("ABCDEFGHI", (8, 12, 10, 50, 20, 18, 22, 32, 40)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    wb.save(str(path))
    return path


def export_scans(rows: list[dict], path: str | Path) -> Path:
    path = Path(path)
    data = [scan_row(r) for r in rows]
    if path.suffix.lower() == ".xlsx":
        return write_xlsx(path, FULL_HEADERS, data)
    return write_csv(path, FULL_HEADERS, data)
