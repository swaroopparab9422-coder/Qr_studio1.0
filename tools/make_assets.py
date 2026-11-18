"""Generates assets/logo/logo.png and assets/icons/app.ico (run once; files are committed)."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PETROL, CREAM, ORANGE = "#24505A", "#F0EBD8", "#FF5A1E"


def make(size: int = 512) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=PETROL)
    u = size / 16

    def finder(x, y, col):
        d.rectangle([x * u, y * u, (x + 5) * u, (y + 5) * u], fill=col)
        d.rectangle([(x + 1) * u, (y + 1) * u, (x + 4) * u, (y + 4) * u], fill=PETROL)
        d.rectangle([(x + 2) * u, (y + 2) * u, (x + 3) * u, (y + 3) * u], fill=col)

    finder(2.5, 2.5, CREAM)
    finder(8.5, 2.5, CREAM)
    finder(2.5, 8.5, CREAM)
    for (x, y) in [(8.5, 8.5), (10.5, 8.5), (12.5, 8.5), (8.5, 10.5), (12.5, 10.5), (10.5, 12.5), (12.5, 12.5)]:
        d.rectangle([x * u, y * u, (x + 1.4) * u, (y + 1.4) * u], fill=ORANGE)
    return img


if __name__ == "__main__":
    (ROOT / "assets" / "logo").mkdir(parents=True, exist_ok=True)
    (ROOT / "assets" / "icons").mkdir(parents=True, exist_ok=True)
    logo = make(512)
    logo.save(ROOT / "assets" / "logo" / "logo.png")
    logo.save(ROOT / "assets" / "icons" / "app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("assets written")
