"""QR payload builders and image/SVG rendering. Works fully offline."""
from __future__ import annotations

import base64
import io
import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import quote, urlparse

from PIL import Image, ImageColor, ImageDraw

EC_LEVELS = {"L (7%)": "L", "M (15%)": "M", "Q (25%)": "Q", "H (30%)": "H"}
LOGO_FRACTION = 0.22


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    placeholder: str = ""
    kind: str = "text"          # text | multiline | combo | check
    required: bool = True
    options: tuple = ()


QR_TYPES: dict[str, list[Field]] = {
    "Plain Text": [Field("text", "Text", "Type any text", "multiline")],
    "Website URL": [Field("url", "Website address", "https://example.com")],
    "PDF URL": [Field("url", "Public PDF link", "https://example.com/catalog.pdf")],
    "Email Address": [Field("address", "Email address", "name@example.com"),
                      Field("subject", "Subject", "", required=False),
                      Field("body", "Message", "", "multiline", False)],
    "Phone Number": [Field("number", "Phone number", "+91 98765 43210")],
    "WhatsApp": [Field("number", "WhatsApp number (with country code)", "919876543210"),
                 Field("message", "Pre-filled message", "", "multiline", False)],
    "Wi-Fi Network": [Field("ssid", "Network name (SSID)"),
                      Field("password", "Password", "", required=False),
                      Field("security", "Security", "", "combo", True, ("WPA/WPA2/WPA3", "WEP", "None")),
                      Field("hidden", "Hidden network", "This network is hidden", "check", False)],
    "Contact Details / vCard": [Field("first", "First name", required=False), Field("last", "Last name", required=False),
                                Field("org", "Company", required=False), Field("title", "Job title", required=False),
                                Field("phone", "Phone", required=False), Field("email", "Email", required=False),
                                Field("website", "Website", required=False), Field("address", "Address", required=False)],
    "SMS": [Field("number", "Phone number", "+91 98765 43210"), Field("message", "Message", "", "multiline", False)],
    "Google Maps Location": [Field("location", "Address, place or latitude,longitude", "16.7050, 74.2433")],
    "Instagram": [Field("username", "Username or profile link", "@yourname")],
    "Facebook": [Field("page", "Page name or link", "yourpage")],
    "YouTube": [Field("channel", "Video/channel link or @handle", "@yourchannel")],
    "LinkedIn": [Field("profile", "Profile name or link", "your-name")],
    "Custom URL": [Field("url", "URL", "https://example.com/anything")],
}

_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _c(v) -> str:
    return (v or "").strip()


def normalize_url(u: str, allow_any_scheme: bool = False) -> str:
    u = _c(u)
    if not u:
        raise ValueError("Please enter a web address.")
    if re.search(r"\s", u):
        raise ValueError("A web address cannot contain spaces.")
    if allow_any_scheme and re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", u) and not re.match(r"^[a-zA-Z]:[\\/]", u):
        return u
    if not _SCHEME.match(u):
        u = "https://" + u
    p = urlparse(u)
    if p.scheme not in ("http", "https") or not p.netloc or "." not in p.netloc and p.netloc != "localhost":
        raise ValueError("Enter a valid web address, for example https://example.com")
    return u


def is_public_host(host: str) -> bool:
    host = (host or "").lower().strip("[]")
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".lan", ".home")):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        return "." in host


def _pdf_url(u: str) -> str:
    u = _c(u)
    if re.match(r"^[a-zA-Z]:[\\/]", u) or u.startswith(("\\\\", "/", "file:", "~")):
        raise ValueError("A PDF QR code needs a public web link (https://...), not a file on this computer. "
                         "Upload the PDF to your website, Google Drive or Dropbox and paste its public link.")
    url = normalize_url(u)
    if not is_public_host(urlparse(url).hostname or ""):
        raise ValueError("That link points to a private/local address. Use a publicly accessible PDF link.")
    return url


def _esc_wifi(v: str) -> str:
    return re.sub(r'([\\;,:"])', r"\\\1", v)


def _esc_vcard(v: str) -> str:
    return v.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _digits(v: str, lo: int, hi: int, what: str) -> str:
    d = re.sub(r"\D", "", _c(v))
    if not lo <= len(d) <= hi:
        raise ValueError(f"Enter a valid {what} ({lo}-{hi} digits).")
    return d


def _phone(v: str) -> str:
    raw = _c(v)
    if not re.fullmatch(r"[+\d\s\-().]+", raw or "x"):
        raise ValueError("Phone numbers may only contain digits, spaces and + - ( ).")
    d = re.sub(r"\D", "", raw)
    if not 5 <= len(d) <= 15:
        raise ValueError("Enter a valid phone number (5-15 digits).")
    return ("+" if raw.lstrip().startswith("+") else "") + d


def _social(value: str, host: str, base: str, pattern: str, label: str) -> str:
    v = _c(value)
    if not v:
        raise ValueError(f"Please enter the {label}.")
    if v.lower().startswith(("http://", "https://")) or host in v.lower():
        return normalize_url(v)
    v = v.lstrip("@")
    if not re.fullmatch(pattern, v):
        raise ValueError(f"'{v}' is not a valid {label}.")
    return base.format(v)


def build_payload(qr_type: str, values: dict) -> str:
    """Return the text to encode. Raises ValueError with a friendly message if input is invalid."""
    g = lambda k: _c(values.get(k))
    t = qr_type
    if t == "Plain Text":
        if not g("text"):
            raise ValueError("Please type some text.")
        return values.get("text", "").strip()
    if t == "Website URL":
        return normalize_url(g("url"))
    if t == "PDF URL":
        return _pdf_url(g("url"))
    if t == "Custom URL":
        return normalize_url(g("url"), allow_any_scheme=True)
    if t == "Email Address":
        if not _EMAIL.match(g("address")):
            raise ValueError("Enter a valid email address.")
        parts = []
        if g("subject"):
            parts.append("subject=" + quote(g("subject")))
        if g("body"):
            parts.append("body=" + quote(g("body")))
        return "mailto:" + g("address") + ("?" + "&".join(parts) if parts else "")
    if t == "Phone Number":
        return "tel:" + _phone(g("number"))
    if t == "WhatsApp":
        n = _digits(g("number"), 6, 15, "WhatsApp number with country code")
        return f"https://wa.me/{n}" + (f"?text={quote(g('message'))}" if g("message") else "")
    if t == "SMS":
        return f"SMSTO:{_phone(g('number'))}:{g('message')}"
    if t == "Wi-Fi Network":
        if not g("ssid"):
            raise ValueError("Enter the Wi-Fi network name.")
        sec = {"WPA/WPA2/WPA3": "WPA", "WEP": "WEP", "None": "nopass"}.get(g("security") or "WPA/WPA2/WPA3", "WPA")
        if sec != "nopass" and not _c(values.get("password")):
            raise ValueError("Enter the Wi-Fi password (or choose Security: None).")
        pw = "" if sec == "nopass" else _esc_wifi(values.get("password", ""))
        hidden = "H:true;" if values.get("hidden") else ""
        return f"WIFI:T:{sec};S:{_esc_wifi(g('ssid'))};P:{pw};{hidden};"
    if t == "Contact Details / vCard":
        if not (g("first") or g("last") or g("org")):
            raise ValueError("Enter at least a name or company.")
        if g("email") and not _EMAIL.match(g("email")):
            raise ValueError("The email address looks invalid.")
        lines = ["BEGIN:VCARD", "VERSION:3.0",
                 f"N:{_esc_vcard(g('last'))};{_esc_vcard(g('first'))};;;",
                 f"FN:{_esc_vcard((g('first') + ' ' + g('last')).strip() or g('org'))}"]
        if g("org"):
            lines.append("ORG:" + _esc_vcard(g("org")))
        if g("title"):
            lines.append("TITLE:" + _esc_vcard(g("title")))
        if g("phone"):
            lines.append("TEL;TYPE=CELL:" + _phone(g("phone")))
        if g("email"):
            lines.append("EMAIL:" + g("email"))
        if g("website"):
            lines.append("URL:" + normalize_url(g("website")))
        if g("address"):
            lines.append("ADR:;;" + _esc_vcard(g("address")) + ";;;;")
        lines.append("END:VCARD")
        return "\n".join(lines)
    if t == "Google Maps Location":
        loc = g("location")
        if not loc:
            raise ValueError("Enter an address, place name or coordinates.")
        m = re.fullmatch(r"(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)", loc)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
            if abs(lat) > 90 or abs(lng) > 180:
                raise ValueError("Latitude must be within +/-90 and longitude within +/-180.")
            return f"https://www.google.com/maps?q={m.group(1)},{m.group(2)}"
        if loc.lower().startswith("http"):
            return normalize_url(loc)
        return "https://www.google.com/maps/search/?api=1&query=" + quote(loc)
    if t == "Instagram":
        return _social(g("username"), "instagram.com", "https://www.instagram.com/{}/", r"[A-Za-z0-9._]{1,30}", "Instagram username")
    if t == "Facebook":
        return _social(g("page"), "facebook.com", "https://www.facebook.com/{}", r"[A-Za-z0-9._\-]{2,}", "Facebook page name")
    if t == "LinkedIn":
        return _social(g("profile"), "linkedin.com", "https://www.linkedin.com/in/{}", r"[A-Za-z0-9._\-%]{2,}", "LinkedIn profile name")
    if t == "YouTube":
        v = g("channel")
        if not v:
            raise ValueError("Enter a YouTube link or @handle.")
        if v.lower().startswith(("http", "www.", "youtube.", "youtu.be")):
            return normalize_url(v)
        v = v.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9._\-]{3,}", v):
            raise ValueError("That is not a valid YouTube handle.")
        return f"https://www.youtube.com/@{v}"
    raise ValueError(f"Unknown QR type: {qr_type}")


# ---------------------------------------------------------------- rendering
def qr_matrix(data: str, ec: str = "M") -> list[list[bool]]:
    try:
        import qrcode
        from qrcode import constants as k
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The 'qrcode' package is not installed. Run: pip install -r requirements.txt") from exc
    levels = {"L": k.ERROR_CORRECT_L, "M": k.ERROR_CORRECT_M, "Q": k.ERROR_CORRECT_Q, "H": k.ERROR_CORRECT_H}
    qr = qrcode.QRCode(version=None, error_correction=levels.get(ec, k.ERROR_CORRECT_M), box_size=1, border=0)
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except Exception as exc:
        if "overflow" in type(exc).__name__.lower() or "too large" in str(exc).lower():
            raise ValueError("There is too much data for one QR code. Shorten the text or use a lower error correction.") from exc
        raise
    return [[bool(c) for c in row] for row in qr.get_matrix()]


def _rgb(c: str):
    return ImageColor.getrgb(c)


def make_qr_image(data: str, size: int = 1024, fg: str = "#000000", bg: str = "#FFFFFF",
                  ec: str = "M", logo: str | None = None, border: int = 4) -> Image.Image:
    """Square, crisp (whole pixels per module) QR image of exactly `size` px (or the minimum needed)."""
    if logo:
        ec = "H"
    m = qr_matrix(data, ec)
    n = len(m) + 2 * border
    size = max(size, n)
    small = Image.new("RGB", (n, n), _rgb(bg))
    px, fgc = small.load(), _rgb(fg)
    for r, row in enumerate(m):
        for c, v in enumerate(row):
            if v:
                px[c + border, r + border] = fgc
    mod = size // n
    img = small.resize((mod * n, mod * n), Image.NEAREST)
    if img.width != size:
        canvas = Image.new("RGB", (size, size), _rgb(bg))
        canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
        img = canvas
    if logo:
        img = _paste_logo(img, logo, bg)
    return img


def _paste_logo(img: Image.Image, path: str, bg: str) -> Image.Image:
    try:
        lg = Image.open(path).convert("RGBA")
    except Exception as exc:
        raise ValueError(f"Could not open the logo image: {exc}") from exc
    box = int(img.width * LOGO_FRACTION)
    lg.thumbnail((box, box), Image.LANCZOS)
    pad = max(4, int(box * 0.10))
    plate = Image.new("RGBA", (lg.width + 2 * pad, lg.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([0, 0, plate.width - 1, plate.height - 1], radius=pad, fill=_rgb(bg) + (255,))
    plate.alpha_composite(lg, (pad, pad))
    out = img.convert("RGBA")
    out.alpha_composite(plate, ((img.width - plate.width) // 2, (img.height - plate.height) // 2))
    return out.convert("RGB")


def make_qr_svg(data: str, fg: str = "#000000", bg: str = "#FFFFFF", ec: str = "M",
                logo: str | None = None, border: int = 4) -> str:
    if logo:
        ec = "H"
    m = qr_matrix(data, ec)
    n = len(m) + 2 * border
    d = []
    for r, row in enumerate(m):
        c = 0
        while c < len(row):
            if row[c]:
                s = c
                while c < len(row) and row[c]:
                    c += 1
                d.append(f"M{s + border} {r + border}h{c - s}v1h-{c - s}z")
            else:
                c += 1
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {n} {n}" '
           f'width="{n * 10}" height="{n * 10}" shape-rendering="crispEdges">',
           f'<rect width="{n}" height="{n}" fill="{bg}"/>', f'<path d="{"".join(d)}" fill="{fg}"/>']
    if logo:
        try:
            lg = Image.open(logo).convert("RGBA")
            side = n * LOGO_FRACTION
            lg.thumbnail((256, 256), Image.LANCZOS)
            buf = io.BytesIO()
            lg.save(buf, "PNG")
            w, h = (side, side * lg.height / lg.width) if lg.width >= lg.height else (side * lg.width / lg.height, side)
            x, y, pad = (n - w) / 2, (n - h) / 2, side * 0.1
            svg.append(f'<rect x="{x - pad:.2f}" y="{y - pad:.2f}" width="{w + 2 * pad:.2f}" height="{h + 2 * pad:.2f}" rx="{pad:.2f}" fill="{bg}"/>')
            svg.append(f'<image x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
                       f'href="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"/>')
        except Exception as exc:
            raise ValueError(f"Could not open the logo image: {exc}") from exc
    svg.append("</svg>")
    return "".join(svg)


# ---------------------------------------------------------------- quality
def _lum(c: str) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(c)[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def scannability_notes(fg: str, bg: str, logo: str | None, ec: str, payload_len: int) -> list[str]:
    notes = []
    if _lum(fg) >= _lum(bg):
        notes.append("Light-on-dark (inverted) codes are not read by many scanners. Use a dark foreground on a light background.")
    elif contrast_ratio(fg, bg) < 4:
        notes.append("Contrast is low. Choose a darker foreground or lighter background so scanners can read it.")
    if logo and ec != "H":
        notes.append("A logo needs error correction H, so H is used automatically.")
    if payload_len > 600:
        notes.append("A lot of data makes a dense code. Print it larger.")
    return notes


def verify_decodable(img: Image.Image, expected: str) -> bool | None:
    """Try to read the generated image back with OpenCV. None = OpenCV not available."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    text, _pts, _ = cv2.QRCodeDetector().detectAndDecode(arr)
    return text.replace("\r\n", "\n") == expected.replace("\r\n", "\n")
