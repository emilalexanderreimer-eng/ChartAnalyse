@echo off
REM ============================================================
REM  Report-Viewer per Doppelklick starten.
REM  Oeffnet http://localhost:8000 im Browser und bleibt laufen.
REM  Fenster schliessen oder Strg+C beendet den Viewer.
REM ============================================================
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" viewer.py %*
) else (
  python viewer.py %*
)
pause
