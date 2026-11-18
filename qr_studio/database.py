"""SQLite storage: scan history, saved codes and counters."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .paths import database_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    scan_type TEXT,
    code_format TEXT,
    scanned_at TEXT NOT NULL,
    source TEXT,
    generated_details TEXT,
    export_path TEXT
);
CREATE TABLE IF NOT EXISTS codes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    code_type TEXT NOT NULL,
    data TEXT NOT NULL,
    options TEXT,
    created_at TEXT NOT NULL,
    export_path TEXT
);
CREATE TABLE IF NOT EXISTS stats(
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);
"""


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else database_dir() / "qr_studio.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # -- low level ---------------------------------------------------------
    def execute(self, sql: str, params=()) -> int:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur.lastrowid

    def query(self, sql: str, params=()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def scalar(self, sql: str, params=(), default=0):
        rows = self.query(sql, params)
        if not rows:
            return default
        v = list(rows[0].values())[0]
        return default if v is None else v

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def backup(self, dest: str | Path) -> None:
        with self._lock:
            target = sqlite3.connect(str(dest))
            try:
                self.conn.backup(target)
            finally:
                target.close()

    # -- scans -------------------------------------------------------------
    def add_scan(self, content: str, scan_type: str, code_format: str, source: str) -> int:
        details, export = "", ""
        match = self.query(
            "SELECT name, export_path FROM codes WHERE data=? ORDER BY id DESC LIMIT 1", (content,))
        if match:
            details = f"Matches saved code: {match[0]['name']}"
            export = match[0]["export_path"] or ""
        return self.execute(
            "INSERT INTO scans(content, scan_type, code_format, scanned_at, source, generated_details, export_path)"
            " VALUES(?,?,?,?,?,?,?)",
            (content, scan_type, code_format, now_str(), source, details, export))

    def search_scans(self, text: str = "", scan_type: str = "", source: str = "", limit: int = 5000) -> list[dict]:
        sql, params = "SELECT * FROM scans WHERE 1=1", []
        if text:
            like = f"%{text}%"
            sql += " AND (content LIKE ? OR scan_type LIKE ? OR code_format LIKE ? OR source LIKE ? OR scanned_at LIKE ?)"
            params += [like] * 5
        if scan_type:
            sql += " AND scan_type=?"
            params.append(scan_type)
        if source:
            sql += " AND source LIKE ?"
            params.append(f"{source}%")
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return self.query(sql, params)

    def scan_types(self) -> list[str]:
        return [r["scan_type"] for r in self.query(
            "SELECT DISTINCT scan_type FROM scans WHERE scan_type IS NOT NULL ORDER BY scan_type")]

    def delete_scans(self, ids: list[int]) -> None:
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            self.execute(f"DELETE FROM scans WHERE id IN ({','.join('?' * len(chunk))})", chunk)

    def clear_scans(self) -> None:
        self.execute("DELETE FROM scans")

    def count_scans_today(self) -> int:
        return int(self.scalar("SELECT COUNT(*) FROM scans WHERE scanned_at >= ?",
                               (datetime.now().strftime("%Y-%m-%d 00:00:00"),)))

    # -- saved codes ---------------------------------------------------------
    def add_code(self, name: str, kind: str, code_type: str, data: str, options: str,
                 export_path: str = "") -> int:
        return self.execute(
            "INSERT INTO codes(name, kind, code_type, data, options, created_at, export_path) VALUES(?,?,?,?,?,?,?)",
            (name, kind, code_type, data, options, now_str(), export_path))

    def update_code_export(self, code_id: int, path: str) -> None:
        self.execute("UPDATE codes SET export_path=? WHERE id=?", (path, code_id))

    def list_codes(self, text: str = "", kind: str = "") -> list[dict]:
        sql, params = "SELECT * FROM codes WHERE 1=1", []
        if text:
            like = f"%{text}%"
            sql += " AND (name LIKE ? OR code_type LIKE ? OR data LIKE ?)"
            params += [like] * 3
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        sql += " ORDER BY id DESC"
        return self.query(sql, params)

    def get_code(self, code_id: int) -> dict | None:
        rows = self.query("SELECT * FROM codes WHERE id=?", (code_id,))
        return rows[0] if rows else None

    def delete_codes(self, ids: list[int]) -> None:
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            self.execute(f"DELETE FROM codes WHERE id IN ({','.join('?' * len(chunk))})", chunk)

    # -- counters ------------------------------------------------------------
    def bump_stat(self, key: str, n: int = 1) -> None:
        self.execute(
            "INSERT INTO stats(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = value + ?",
            (key, n, n))

    def get_stat(self, key: str) -> int:
        return int(self.scalar("SELECT value FROM stats WHERE key=?", (key,)))
