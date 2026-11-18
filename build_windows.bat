@echo off
REM ===== QR Studio - Windows EXE build =====
REM Needs Python 3.11+ (https://www.python.org/downloads/ - tick "Add python.exe to PATH").
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Creating virtual environment...
    py -3.11 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 goto :fail
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

if not exist assets\icons\app.ico python tools\make_assets.py

echo Building EXE...
pyinstaller --noconfirm --clean --windowed --name "QR Studio" ^
  --icon assets\icons\app.ico ^
  --add-data "assets;assets" ^
  --collect-data barcode --collect-submodules barcode ^
  --collect-submodules serial ^
  --hidden-import PySide6.QtSvg --hidden-import PySide6.QtPrintSupport ^
  main.py
if errorlevel 1 goto :fail

echo.
echo Build finished:  dist\QR Studio\QR Studio.exe

where iscc >nul 2>nul
if %errorlevel%==0 (
    echo Building installer with Inno Setup...
    iscc installer.iss
) else (
    echo Inno Setup not found - skipping the installer. See README for the optional installer step.
)
if not defined CI pause
exit /b 0

:fail
echo.
echo BUILD FAILED - read the messages above.
if not defined CI pause
exit /b 1
