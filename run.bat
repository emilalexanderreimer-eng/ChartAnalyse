@echo off
REM ============================================================
REM  Chartanalyse - Start per Doppelklick
REM  Beim ersten Lauf wird automatisch eine virtuelle Umgebung
REM  (.venv) angelegt und alle Pakete installiert.
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [Setup] Erstelle virtuelle Umgebung ^(einmalig^)...
  python -m venv .venv
  if errorlevel 1 (
    echo [Fehler] Python wurde nicht gefunden. Bitte Python 3 installieren.
    pause
    exit /b 1
  )
  echo [Setup] Installiere Pakete ^(kann ein paar Minuten dauern^)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

".venv\Scripts\python.exe" main.py %*
echo.
pause
