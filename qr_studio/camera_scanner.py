"""Optional webcam scanning with OpenCV (QR via QRCodeDetector, barcodes via cv2.barcode when available)."""
from __future__ import annotations


def opencv_available() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


class FrameDecoder:
    def __init__(self):
        import cv2
        self.cv2 = cv2
        self.qr = cv2.QRCodeDetector()
        self.bar = None
        try:
            self.bar = cv2.barcode.BarcodeDetector()
        except Exception:
            try:
                self.bar = cv2.barcode_BarcodeDetector()
            except Exception:
                self.bar = None

    def decode(self, frame) -> list[tuple[str, str]]:
        """Return [(text, format)] found in a BGR frame."""
        found = []
        try:
            text, _pts, _ = self.qr.detectAndDecode(frame)
            if text:
                found.append((text, "QR Code"))
        except Exception:
            pass
        if self.bar is not None:
            try:
                res = self.bar.detectAndDecodeWithType(frame)
                if len(res) == 4:
                    _ok, infos, types, _pts = res
                    for info, typ in zip(infos or [], types or []):
                        if info:
                            found.append((info, str(typ) or "Barcode"))
            except Exception:
                pass
        return found
