@echo off
REM ============================================================
REM  Wird von der Windows-Aufgabenplanung aufgerufen (taeglich).
REM  Laeuft ohne Fenster/Nachfrage, schreibt ein Log und sendet
REM  bei Alerts eine E-Mail. NICHT zum Doppelklicken gedacht
REM  (dafuer run.bat verwenden).
REM ============================================================
cd /d "%~dp0"
if not exist "output" mkdir "output"
".venv\Scripts\pythonw.exe" main.py --no-open --email >> "output\scan.log" 2>&1
