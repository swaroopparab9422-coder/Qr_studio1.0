"""A4 print sheets: compose several codes per page; export to PDF. (Direct printing is done in the UI.)"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .barcode_generator import _font

A4_MM = (210.0, 297.0)


def _px(mm: float, dpi: int) -> int:
    return int(round(mm / 25.4 * dpi))


def build_sheets(items: list[tuple[Image.Image, str]], rows: int = 4, cols: int = 3, margin_mm: float = 10,
                 gap_mm: float = 4, dpi: int = 200, captions: bool = True) -> list[Image.Image]:
    if not items:
        raise ValueError("There is nothing to print.")
    if rows < 1 or cols < 1:
        raise ValueError("Rows and columns must be at least 1.")
    W, H = _px(A4_MM[0], dpi), _px(A4_MM[1], dpi)
    m, g = _px(margin_mm, dpi), _px(gap_mm, dpi)
    cw, ch = (W - 2 * m - (cols - 1) * g) // cols, (H - 2 * m - (rows - 1) * g) // rows
    if cw < 20 or ch < 20:
        raise ValueError("Cells are too small - reduce rows/columns or margins.")
    cap_h = _px(5, dpi) if captions else 0
    font = _font(max(10, _px(2.8, dpi)))
    per_page = rows * cols
    pages = []
    for start in range(0, len(items), per_page):
        page = Image.new("RGB", (W, H), "white")
        dr = ImageDraw.Draw(page)
        for k, (img, cap) in enumerate(items[start:start + per_page]):
            r, c = divmod(k, cols)
            x, y = m + c * (cw + g), m + r * (ch + g)
            s = min(cw / img.width, (ch - cap_h) / img.height)
            im = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS if s < 1 else Image.NEAREST)
            page.paste(im, (x + (cw - im.width) // 2, y + (ch - cap_h - im.height) // 2))
            if captions and cap:
                text = cap if len(cap) <= 34 else cap[:31] + "..."
                dr.text((x + cw / 2, y + ch - cap_h / 2), text, fill="#222222", font=font, anchor="mm")
        pages.append(page)
    return pages


def save_pdf(pages: list[Image.Image], path: str | Path, dpi: int = 200) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(path, "PDF", resolution=float(dpi), save_all=True, append_images=pages[1:])
    return path
