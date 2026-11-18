"""Barcode validation, encoding (python-barcode + built-in UPC-E/Codabar) and rendering with Pillow."""
from __future__ import annotations

import re

from PIL import Image, ImageColor, ImageDraw, ImageFont

BARCODE_TYPES = ["Code 128", "Code 39", "EAN-13", "EAN-8", "UPC-A", "UPC-E", "ITF", "Codabar"]
HINTS = {
    "Code 128": "Any letters, numbers and symbols (ASCII). Best general-purpose choice.",
    "Code 39": "Capital letters A-Z, digits 0-9 and - . $ / + % space.",
    "EAN-13": "12 digits (check digit added) or 13 digits.",
    "EAN-8": "7 digits (check digit added) or 8 digits.",
    "UPC-A": "11 digits (check digit added) or 12 digits.",
    "UPC-E": "6 digits, or number system 0/1 + 6 digits (+ optional check digit).",
    "ITF": "Digits only, an even number of digits.",
    "Codabar": "Digits and - $ : / . + ; A/B/C/D start-stop added automatically.",
}
_LIB_NAME = {"Code 128": "code128", "Code 39": "code39", "EAN-13": "ean13", "EAN-8": "ean8", "UPC-A": "upca", "ITF": "itf"}

_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
_R = ["".join("1" if b == "0" else "0" for b in c) for c in _L]
_G = [c[::-1] for c in _R]
_UPCE_PARITY = ["EEEOOO", "EEOEOO", "EEOOEO", "EEOOOE", "EOEEOO", "EOOEEO", "EOOOEE", "EOEOEO", "EOEOOE", "EOOEOE"]
_CODABAR = {"0": "0000011", "1": "0000110", "2": "0001001", "3": "1100000", "4": "0010010", "5": "1000010",
            "6": "0100001", "7": "0100100", "8": "0110000", "9": "1001000", "-": "0001100", "$": "0011000",
            "A": "0011010", "B": "0101001", "C": "0001011", "D": "0001110"}
_CODABAR.update({":": "1000101", "/": "1010001", ".": "1010100", "+": "0010101"})
_CODE39 = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ -.$/+%")


def ean_check_digit(digits: str) -> int:
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits)))
    return (10 - total % 10) % 10


def _upce_to_upca(ns: str, six: str) -> str:
    a, b, c, d, e, f = six
    if f in "012":
        return ns + a + b + f + "0000" + c + d + e
    if f == "3":
        return ns + a + b + c + "00000" + d + e
    if f == "4":
        return ns + a + b + c + d + "00000" + e
    return ns + a + b + c + d + e + "0000" + f


def validate(kind: str, data: str) -> str:
    """Return the cleaned/complete data string or raise ValueError with a clear reason."""
    d = (data or "").strip()
    if not d:
        raise ValueError("Enter the barcode data.")

    def digits_only(lengths, name):
        if not d.isdigit():
            raise ValueError(f"{name} accepts digits only.")
        if len(d) not in lengths:
            raise ValueError(f"{name} needs {' or '.join(map(str, lengths))} digits (you entered {len(d)}).")

    if kind in ("EAN-13", "EAN-8", "UPC-A"):
        n = {"EAN-13": 13, "EAN-8": 8, "UPC-A": 12}[kind]
        digits_only((n - 1, n), kind)
        body = d[:n - 1]
        chk = ean_check_digit(body)
        if len(d) == n and int(d[-1]) != chk:
            raise ValueError(f"Wrong check digit: the last digit should be {chk}.")
        return body + str(chk)
    if kind == "UPC-E":
        digits_only((6, 7, 8), "UPC-E")
        ns, six = ("0", d) if len(d) == 6 else (d[0], d[1:7])
        if ns not in "01":
            raise ValueError("UPC-E number system must be 0 or 1.")
        chk = ean_check_digit(_upce_to_upca(ns, six)[:11])
        if len(d) == 8 and int(d[7]) != chk:
            raise ValueError(f"Wrong check digit: the last digit should be {chk}.")
        return ns + six + str(chk)
    if kind == "ITF":
        digits_only(tuple(range(2, 81, 2)), "ITF (needs an even number of digits)")
        return d
    if kind == "Code 39":
        d = d.upper()
        bad = sorted({c for c in d if c not in _CODE39})
        if bad:
            raise ValueError("Code 39 cannot contain: " + " ".join(repr(c) for c in bad))
        return d
    if kind == "Code 128":
        bad = sorted({c for c in d if not 32 <= ord(c) <= 126})
        if bad:
            raise ValueError("Code 128 here supports standard keyboard characters only.")
        return d
    if kind == "Codabar":
        d = d.upper()
        body = d[1:-1] if len(d) > 2 and d[0] in "ABCD" and d[-1] in "ABCD" else d
        if not body or any(c not in "0123456789-$:/.+" for c in body):
            raise ValueError("Codabar accepts digits and - $ : / . + only.")
        return d if body is not d else "A" + d + "A"
    raise ValueError(f"Unknown barcode type: {kind}")


def human_text(kind: str, d: str) -> str:
    if kind == "EAN-13":
        return f"{d[0]} {d[1:7]} {d[7:]}"
    if kind == "EAN-8":
        return f"{d[:4]} {d[4:]}"
    if kind == "UPC-A":
        return f"{d[0]} {d[1:6]} {d[6:11]} {d[11]}"
    if kind == "UPC-E":
        return f"{d[0]} {d[1:7]} {d[7]}"
    return d


def encode(kind: str, data: str) -> tuple[str, str]:
    """Return (bar pattern of '1'/'0' modules, human-readable text)."""
    d = validate(kind, data)
    if kind == "UPC-E":
        par = _UPCE_PARITY[int(d[7])]
        if d[0] == "1":
            par = "".join("E" if p == "O" else "O" for p in par)
        bars = "101" + "".join((_L if p == "O" else _G)[int(ch)] for p, ch in zip(par, d[1:7])) + "010101"
        return bars, human_text(kind, d)
    if kind == "Codabar":
        out = []
        for ch in d:
            pat = _CODABAR[ch]
            for i, w in enumerate(pat):
                out.append(("1" if i % 2 == 0 else "0") * (3 if w == "1" else 1))
            out.append("0")
        return "".join(out).rstrip("0"), d
    try:
        import barcode as pb
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The 'python-barcode' package is not installed. Run: pip install -r requirements.txt") from exc
    cls = pb.get_barcode_class(_LIB_NAME[kind])
    code = d[:-1] if kind in ("EAN-13", "EAN-8") else d
    if kind == "UPC-A":
        code = d[:11]
    obj = cls(code, add_checksum=False) if kind == "Code 39" else cls(code)
    bars = "".join(obj.build())
    return bars, human_text(kind, d if kind != "Code 39" else d)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def render_barcode(kind: str, data: str, module_width: int = 3, height: int = 120, show_text: bool = True,
                   fg: str = "#000000", bg: str = "#FFFFFF", scale: float = 1.0, quiet: int = 10) -> Image.Image:
    bars, text = encode(kind, data)
    mw = max(1, int(round(module_width * scale)))
    h = max(20, int(height * scale))
    q = quiet * mw
    fsize = max(10, int(14 * scale * max(1, module_width / 2)))
    font = _font(fsize)
    text_h = int(fsize * 1.6) if show_text else 0
    bars_w = len(bars) * mw
    tw = int(ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=font)) if show_text else 0
    width = max(bars_w + 2 * q, tw + 2 * int(fsize))
    img = Image.new("RGB", (width, h + text_h + int(8 * scale)), ImageColor.getrgb(bg))
    dr = ImageDraw.Draw(img)
    x0 = (width - bars_w) // 2
    i = 0
    while i < len(bars):
        if bars[i] == "1":
            j = i
            while j < len(bars) and bars[j] == "1":
                j += 1
            dr.rectangle([x0 + i * mw, int(4 * scale), x0 + j * mw - 1, int(4 * scale) + h - 1], fill=ImageColor.getrgb(fg))
            i = j
        else:
            i += 1
    if show_text:
        dr.text((width / 2, int(4 * scale) + h + text_h / 2), text, fill=ImageColor.getrgb(fg), font=font, anchor="mm")
    return img


def render_barcode_svg(kind: str, data: str, module_width: int = 3, height: int = 120, show_text: bool = True,
                       fg: str = "#000000", bg: str = "#FFFFFF", quiet: int = 10) -> str:
    bars, text = encode(kind, data)
    mw, text_h = module_width, (28 if show_text else 0)
    width = len(bars) * mw + 2 * quiet * mw
    total_h = height + text_h + 8
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_h}" viewBox="0 0 {width} {total_h}" shape-rendering="crispEdges">',
             f'<rect width="{width}" height="{total_h}" fill="{bg}"/>']
    i = 0
    while i < len(bars):
        if bars[i] == "1":
            j = i
            while j < len(bars) and bars[j] == "1":
                j += 1
            parts.append(f'<rect x="{quiet * mw + i * mw}" y="4" width="{(j - i) * mw}" height="{height}" fill="{fg}"/>')
            i = j
        else:
            i += 1
    if show_text:
        esc = text.replace("&", "&amp;").replace("<", "&lt;")
        parts.append(f'<text x="{width / 2}" y="{height + 4 + 20}" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="18" fill="{fg}">{esc}</text>')
    parts.append("</svg>")
    return "".join(parts)
