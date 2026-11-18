"""Optional device helpers: serial (COM) scanners and a best-effort list of connected USB input devices.

Most USB scanners are HID *keyboards*: Windows cannot tell them apart from your keyboard, so they are
handled by the scanner input box (see scanner.py / ui/scanner_page.py), not here.
"""
from __future__ import annotations

import subprocess
import sys


def serial_available() -> bool:
    try:
        import serial  # noqa: F401
        return True
    except ImportError:
        return False


def list_serial_ports() -> list[tuple[str, str]]:
    """[(port, description)] for scanners that expose a COM/serial interface (USB-CDC / virtual COM mode)."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [(p.device, p.description or "") for p in sorted(list_ports.comports(), key=lambda p: p.device)]


def list_hid_devices() -> list[str]:
    """Names of connected keyboard/HID devices (Windows only). A keyboard-wedge scanner usually appears as a
    generic 'HID Keyboard Device' - it cannot be distinguished from a real keyboard."""
    if not sys.platform.startswith("win"):
        return []
    cmd = ["powershell", "-NoProfile", "-Command",
           "Get-PnpDevice -PresentOnly -Class Keyboard,HIDClass | Select-Object -ExpandProperty FriendlyName"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15, creationflags=0x08000000).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    seen, names = set(), []
    for line in out.splitlines():
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            names.append(line)
    return names
