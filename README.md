# QR Studio

Windows 10/11 desktop app (Python + PySide6) to **create QR codes and barcodes, scan them with a USB scanner or webcam, and record every scan to a CSV or Excel file**. Swiss Cream minimal theme with soft shadows. Works offline; data stays on your computer.

## Features
| Area | What it does |
|---|---|
| Dashboard | Counters, quick actions, recent scans, latest QR preview, recording status |
| QR Code Generator | 15 types (text, URL, PDF URL, email, phone, WhatsApp, Wi-Fi, vCard, SMS, Maps, Instagram, Facebook, YouTube, LinkedIn, custom URL), live preview, size, colours, error correction, centre logo, read-back verification. PDF codes only accept a **public web link** |
| Barcode Generator | Code 128, Code 39, EAN-13, EAN-8, UPC-A, UPC-E, ITF, Codabar; format validation and check digits, width/height/colours, optional numbers |
| Export | PNG, JPG, JPEG, SVG, PDF via Save As; high-resolution; square QR |
| USB Scanner | Keyboard-wedge input box (Enter / Tab / pause suffix), keeps focus, auto type detection, **live recording to .xlsx or .csv**, copy, session table; optional serial (COM) scanners and OpenCV webcam |
| Scan History | Search, filter, copy, delete, clear (with confirmation), export CSV / Excel |
| Saved Codes | Browse, preview, reopen, export again, delete, search |
| Bulk | CSV/XLSX import, background worker, error report, per-file images + ZIP |
| Print | A4 sheets, rows x columns, print preview, PDF, direct Windows printing (from Saved Codes > Print sheet) |
| Settings | Folders, formats, sizes, colours, scanner suffix/focus, theme (Swiss Cream / Petrol Night), database backup |

## Recording scans to CSV / Excel (your main use)
1. Open **USB Scanner**. Choose **Excel (.xlsx)** or **CSV**, a file name (blank = `scans_YYYY-MM-DD`) and a folder.
2. Keep **Save every scan automatically** on. Click the big box (it also re-focuses itself) and scan.
3. Each scan is appended immediately with columns: No., Date, Time, Content, Type, Format, Source. Scanning again the same day keeps adding to the same file.
4. If the file is open in Excel, Windows locks it: scans still go to history and are written as soon as you close the file.
5. **Export now** saves everything from the current session; **Scan History** exports all older scans.

Text starting with `= + - @` is prefixed with `'` in exports so Excel cannot run it as a formula.

### Scanner setup
Most USB scanners work as a keyboard: plug in, click the scan box, scan. If nothing appears, scan the manual's "USB HID keyboard" code. Make sure the scanner sends **Enter** after each scan (default) - or choose Tab / None in the scanner settings.

**Honest limits:** keyboard-wedge scanners look like a normal keyboard to Windows, so QR Studio cannot name the device, and the barcode format (QR/EAN...) is not reported; it is shown as a "probable" guess. Scanners with a COM/serial mode can be connected directly (USB Scanner > Serial).

## Run from source
```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Build the EXE
- Locally: double-click `build_windows.bat` -> `dist\QR Studio\QR Studio.exe`. If [Inno Setup](https://jrsoftware.org/isinfo.php) is installed, `installer\QR_Studio_Setup.exe` is created too.
- **On GitHub (recommended):** upload this folder to a repository. The workflow in `.github/workflows/build-windows.yml` runs the tests, builds the EXE and uploads `QR_Studio_Windows.zip` + installer under *Actions > latest run > Artifacts*. Push a tag like `v1.0.0` to attach them to a Release.

The packaged app stores data in `%LOCALAPPDATA%\QR Studio` (database, settings, log).

## Project layout
`main.py` - entry | `qr_studio/` - engines (QR, barcode, database, scanner logic, recorder, export, bulk, printing) | `ui/` - screens and theme | `tests/` | `assets/` | `build_windows.bat`, `installer.iss`

## Troubleshooting
| Problem | Fix |
|---|---|
| Scan text does not appear | Click the scan box; confirm the scanner is in HID keyboard mode; try the scanner on Notepad |
| Scans appear but run together / nothing is saved | Set the suffix (Enter/Tab/None) to match your scanner |
| "File is open in another program" | Close the Excel/CSV file; queued scans are written on the next scan |
| Webcam does not start | Close other apps using the camera; try camera index 1; allow camera access in Windows Privacy settings |
| EXE blocked by SmartScreen / antivirus | Unsigned apps trigger a warning: More info > Run anyway |
| `qrcode` / `PySide6` not found | Activate the virtual environment and run `pip install -r requirements.txt` |
| Crash | See `qr_studio.log` in the data folder (Settings > Open data folder) |

## Testing status (please read)
Automated tests live in `tests/`. In the environment where this code was written, PySide6, qrcode and python-barcode could not be installed, so **the window itself and the QR/python-barcode image paths have not been run yet**. What was run and passes: payload builders, barcode validation/UPC-E/Codabar encoders, scanner detection/timing, SQLite, CSV/XLSX recorder, CSV-injection guard, print-sheet and bulk-input parsing. The GitHub workflow runs everything, including a headless GUI smoke test, on Windows. **Still to be verified by you on Windows 10 with your scanner:** the full UI, a real scan, EXE build, printing, webcam.
