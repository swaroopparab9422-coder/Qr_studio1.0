import csv
import pytest
from PIL import Image

from qr_studio import barcode_generator as bg
from qr_studio import bulk, export, history, printing, qr_generator as qg, scanner
from qr_studio.database import Database
from qr_studio.recorder import ScanRecorder


def test_payloads():
    assert qg.build_payload("Website URL", {"url": "example.com"}) == "https://example.com"
    assert qg.build_payload("Phone Number", {"number": "+91 98765 43210"}) == "tel:+919876543210"
    assert qg.build_payload("WhatsApp", {"number": "+91 98765 43210", "message": "Hi"}).startswith("https://wa.me/919876543210")
    assert qg.build_payload("Wi-Fi Network", {"ssid": "My;Net", "password": "p:w", "security": "WPA/WPA2/WPA3"}) == "WIFI:T:WPA;S:My\\;Net;P:p\\:w;;"
    with pytest.raises(ValueError):
        qg.build_payload("Email Address", {"address": "nope"})


def test_pdf_url_must_be_public():
    for bad in ("C:\\docs\\a.pdf", "file:///a.pdf", "http://192.168.1.5/a.pdf", "http://localhost/a.pdf"):
        with pytest.raises(ValueError):
            qg.build_payload("PDF URL", {"url": bad})
    assert qg.build_payload("PDF URL", {"url": "https://example.com/a.pdf"}).startswith("https://")


def test_barcode_validation():
    assert bg.validate("EAN-13", "890123456789") == "8901234567890"
    assert bg.validate("UPC-A", "03600029145") == "036000291452"
    assert bg.validate("UPC-E", "0123456") == "01234565"
    assert bg.validate("Codabar", "1234") == "A1234A"
    with pytest.raises(ValueError):
        bg.validate("EAN-13", "8901234567891")
    with pytest.raises(ValueError):
        bg.validate("ITF", "123")
    bars, _ = bg.encode("UPC-E", "01234565")
    assert len(bars) == 51 and bars.startswith("101") and bars.endswith("010101")


def test_qr_image_is_square_and_svg():
    pytest.importorskip("qrcode")
    img = qg.make_qr_image("hello", 600)
    assert img.width == img.height == 600
    assert qg.make_qr_svg("hello").startswith("<svg")


def test_scanner_detection_and_timing():
    assert scanner.detect_type("https://example.com")[0] == "Website URL"
    assert scanner.detect_type("8901234567890")[0] == "Product Barcode"
    t = scanner.BurstTimer()
    for i in range(8):
        t.add(i * 0.01)
    assert t.looks_like_scanner()
    t.reset()
    for i in range(8):
        t.add(i * 0.3)
    assert not t.looks_like_scanner()


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_recorder_appends_and_continues(tmp_path, fmt):
    pytest.importorskip("openpyxl")
    r = ScanRecorder(tmp_path, fmt)
    r.add("=1+1", "Text", "", "USB")
    r.add("hello", "Plain Text", "", "USB")
    assert ScanRecorder(tmp_path, fmt).rows_in_file == 2


def test_database_history_and_codes(tmp_path):
    db = Database(tmp_path / "t.db")
    db.add_code("n", "qr", "Plain Text", "hello", "{}")
    db.add_scan("hello", "Plain Text", "", "USB")
    assert db.search_scans("hel")[0]["generated_details"].startswith("Matches")
    assert db.count_scans_today() == 1
    db.bump_stat("x", 2)
    assert db.get_stat("x") == 2
    db.backup(tmp_path / "b.db")
    assert (tmp_path / "b.db").exists()


def test_bulk_and_print(tmp_path):
    pytest.importorskip("qrcode")
    src = tmp_path / "in.csv"
    src.write_text("name,type,data\nA,Website URL,example.com\nB,Email Address,bad\n", encoding="utf-8")
    res = bulk.generate_bulk(export.read_rows(src), "qr", {"type": "Plain Text", "size": 300, "fg": "#000000", "bg": "#FFFFFF", "ec": "M"}, tmp_path, "PNG")
    assert len(res.files) == 1 and len(res.errors) == 1 and res.zip_path.exists()
    pages = printing.build_sheets([(Image.new("RGB", (300, 300), "black"), "x")] * 14, rows=4, cols=3)
    assert len(pages) == 2


def test_csv_injection_guard(tmp_path):
    p = history.write_csv(tmp_path / "a.csv", ["c"], [["=cmd"], ["ok"]])
    assert list(csv.reader(open(p, encoding="utf-8-sig")))[1][0] == "'=cmd"
