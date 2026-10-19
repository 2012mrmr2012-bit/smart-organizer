@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== Smart Organizer: build =====

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python is not installed. Install it from python.org and tick "Add to PATH".
  pause & exit /b 1
)

echo [1/5] Creating virtual environment...
%PY% -m venv .venv || (echo [ERROR] venv failed & pause & exit /b 1)
call .venv\Scripts\activate.bat

echo [2/5] Installing dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller || (echo [ERROR] pip failed & pause & exit /b 1)

echo [3/5] Building the app with PyInstaller...
if exist app.png if not exist app.ico (
  pip install pillow >nul
  python make_icon.py
)
set ICONARGS=
if exist app.ico (
  set ICONARGS=--icon app.ico --add-data "app.ico;."
) else (
  echo [!] app.ico not found - building without a custom icon. Put app.png next to this file to add one.
)
pyinstaller --noconfirm --clean --windowed --name SmartOrganizer --collect-all pymupdf --collect-data docx %ICONARGS% organizer_gui.py || (echo [ERROR] PyInstaller failed & pause & exit /b 1)

echo [4/5] Building the installer with Inno Setup...
if not exist installer_output mkdir installer_output
set ISCC=
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if "%ISCC%"=="" (
  echo [!] Inno Setup not found - skipping Setup.exe. Install Inno Setup 6 from https://jrsoftware.org/isdl.php to get it.
) else (
  "%ISCC%" installer.iss || (echo [ERROR] Inno Setup failed & pause & exit /b 1)
)

echo [5/5] Building the portable zip...
> "dist\SmartOrganizer\portable.txt" echo portable
if exist installer_output\SmartOrganizer_Portable.zip del installer_output\SmartOrganizer_Portable.zip
tar -a -c -f installer_output\SmartOrganizer_Portable.zip -C dist SmartOrganizer

echo.
echo ===== DONE =====
echo Output folder: installer_output
echo   SmartOrganizer_Setup.exe     (installer)
echo   SmartOrganizer_Portable.zip  (portable)
explorer installer_output
pause
