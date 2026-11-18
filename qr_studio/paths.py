"""Locations of bundled resources and user data (works from source and from the PyInstaller EXE)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


def data_dir() -> Path:
    """Writable folder for database, settings and default exports.

    Source checkout: the project folder. Packaged EXE: %LOCALAPPDATA%\\QR Studio
    (Program Files is not writable, so we never store data next to the EXE).
    """
    if is_frozen():
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "QR Studio"
    else:
        root = Path(__file__).resolve().parent.parent
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_dir() -> Path:
    p = data_dir() / "database"
    p.mkdir(parents=True, exist_ok=True)
    return p


def output_dir() -> Path:
    p = data_dir() / "output"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_dirs() -> None:
    database_dir()
    output_dir()
