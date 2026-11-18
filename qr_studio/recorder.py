"""Live scan recorder: appends every scan to a CSV or Excel file as it happens."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .history import HEADERS, safe_cell


class RecorderError(Exception):
    pass


class ScanRecorder:
    def __init__(self, folder: str | Path, fmt: str = "xlsx", filename: str | None = None):
        fmt = fmt.lower().lstrip(".")
        if fmt not in ("csv", "xlsx"):
            raise ValueError("Format must be csv or xlsx")
        self.fmt = fmt
        self.path = Path(folder) / (filename or f"scans_{datetime.now():%Y-%m-%d}.{fmt}")
        if self.path.suffix.lower() != "." + fmt:
            self.path = self.path.with_suffix("." + fmt)
        self.pending: list[list] = []
        self.rows_in_file = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rows_in_file = self._count_rows()

    def _count_rows(self) -> int:
        if not self.path.exists():
            return 0
        try:
            if self.fmt == "csv":
                with open(self.path, newline="", encoding="utf-8-sig") as f:
                    return max(0, sum(1 for _ in csv.reader(f)) - 1)
            from openpyxl import load_workbook
            wb = load_workbook(str(self.path), read_only=True)
            try:
                return max(0, (wb.worksheets[0].max_row or 1) - 1)
            finally:
                wb.close()
        except Exception as exc:
            raise RecorderError(f"Cannot read the existing file: {exc}") from exc

    def add(self, content: str, scan_type: str, code_format: str, source: str, when: datetime | None = None) -> int:
        """Queue one scan and write everything queued. Returns rows written; raises RecorderError (rows stay queued)."""
        when = when or datetime.now()
        n = self.rows_in_file + len(self.pending) + 1
        self.pending.append([n, when.strftime("%Y-%m-%d"), when.strftime("%H:%M:%S"), content, scan_type, code_format, source])
        return self.flush()

    def flush(self) -> int:
        if not self.pending:
            return 0
        rows = [[safe_cell(c) for c in r] for r in self.pending]
        try:
            if self.fmt == "csv":
                new = not self.path.exists()
                with open(self.path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
                    w = csv.writer(f)
                    if new:
                        w.writerow(HEADERS)
                    w.writerows(rows)
            else:
                self._write_xlsx(rows)
        except PermissionError as exc:
            raise RecorderError("The file is open in another program (Excel?). Close it - pending scans will be saved next.") from exc
        except OSError as exc:
            raise RecorderError(f"Could not write the file: {exc}") from exc
        written = len(rows)
        self.rows_in_file += written
        self.pending.clear()
        return written

    def _write_xlsx(self, rows: list[list]) -> None:
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Font
        if self.path.exists():
            wb = load_workbook(str(self.path))
            ws = wb.worksheets[0]
        else:
            wb = Workbook()
            ws = wb.active
            ws.title = "Scans"
            ws.append(HEADERS)
            for c in ws[1]:
                c.font = Font(bold=True)
            for col, width in zip("ABCDEFG", (8, 12, 10, 50, 20, 18, 22)):
                ws.column_dimensions[col].width = width
            ws.freeze_panes = "A2"
        for r in rows:
            ws.append(r)
        wb.save(str(self.path))
