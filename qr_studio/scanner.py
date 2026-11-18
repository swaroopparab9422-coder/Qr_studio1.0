"""Scanner logic that needs no GUI: data-type detection and keyboard-wedge timing heuristics."""
from __future__ import annotations

import re
import time

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL = re.compile(r"^(https?://|www\.)\S+$", re.I)


def ean_ok(d: str) -> bool:
    if not d.isdigit() or len(d) < 2:
        return False
    total = sum(int(x) * (3 if i % 2 == 0 else 1) for i, x in enumerate(reversed(d[:-1])))
    return (10 - total % 10) % 10 == int(d[-1])


def detect_type(text: str) -> tuple[str, str]:
    """Return (data type, probable format). The format is only a guess - keyboard-wedge scanners do not report it."""
    t = (text or "").strip()
    low = t.lower()
    if low.startswith("wifi:"):
        return "Wi-Fi Network", "QR Code"
    if low.startswith("begin:vcard"):
        return "Contact (vCard)", "QR Code"
    if low.startswith("mecard:"):
        return "Contact (MECARD)", "QR Code"
    if low.startswith(("smsto:", "sms:")):
        return "SMS", "QR Code"
    if low.startswith("tel:"):
        return "Phone Number", "QR Code"
    if low.startswith("mailto:") or _EMAIL.match(t):
        return "Email Address", "QR Code" if low.startswith("mailto:") else ""
    if low.startswith("geo:") or "google.com/maps" in low or "maps.app.goo.gl" in low:
        return "Location (Maps)", "QR Code"
    if "wa.me/" in low or "api.whatsapp.com" in low:
        return "WhatsApp", "QR Code"
    if _URL.match(t):
        for host, name in (("instagram.com", "Instagram link"), ("facebook.com", "Facebook link"), ("fb.com", "Facebook link"),
                           ("youtube.com", "YouTube link"), ("youtu.be", "YouTube link"), ("linkedin.com", "LinkedIn link")):
            if host in low:
                return name, "QR Code"
        if re.search(r"\.pdf(\?|#|$)", low):
            return "PDF Link", "QR Code"
        return "Website URL", "QR Code"
    if t.isdigit():
        if len(t) == 13 and ean_ok(t):
            return "Product Barcode", "EAN-13 (probable)"
        if len(t) == 12 and ean_ok(t):
            return "Product Barcode", "UPC-A (probable)"
        if len(t) == 8 and ean_ok(t):
            return "Product Barcode", "EAN-8 (probable)"
        return "Numeric Code", ""
    if re.fullmatch(r"[A-Z0-9\-. $/+%]+", t):
        return "Alphanumeric Code", ""
    return "Plain Text", ""


class BurstTimer:
    """Tells fast scanner bursts from human typing using the time between key presses."""

    def __init__(self, max_avg_s: float = 0.05, min_chars: int = 4):
        self.max_avg_s, self.min_chars = max_avg_s, min_chars
        self.stamps: list[float] = []

    def add(self, now: float | None = None) -> None:
        self.stamps.append(time.monotonic() if now is None else now)

    def reset(self) -> None:
        self.stamps.clear()

    def looks_like_scanner(self) -> bool:
        if len(self.stamps) < self.min_chars:
            return False
        gaps = [b - a for a, b in zip(self.stamps, self.stamps[1:])]
        return sum(gaps) / len(gaps) <= self.max_avg_s
