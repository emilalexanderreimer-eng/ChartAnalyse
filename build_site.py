"""
Baut aus dem output/-Ordner eine statische Seite (site/) fuer GitHub Pages.

- Der NEUESTE Report wird zur Startseite (site/index.html).
- Alle erzeugten Report-/CSV-Dateien werden mitkopiert (per Datum-URL erreichbar).

Wird in der GitHub-Action nach dem Scan ausgefuehrt. Lokal nutzbar via:
    python build_site.py
"""
from __future__ import annotations

import os
import re
import shutil

import config as cfg

_REPORT_RE = re.compile(r"^alerts_\d{4}-\d{2}-\d{2}_\d{4}\.html$")

_PLACEHOLDER = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<title>Chartanalyse</title></head>
<body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;padding:40px">
<h1>Chartanalyse</h1><p>Noch kein Report vorhanden.</p></body></html>"""


def build(output_dir: str = None, site_dir: str = "site") -> str:
    output_dir = output_dir or cfg.OUTPUT_DIR
    os.makedirs(site_dir, exist_ok=True)

    reports = []
    if os.path.isdir(output_dir):
        reports = sorted(
            (f for f in os.listdir(output_dir) if _REPORT_RE.match(f)), reverse=True
        )

    # alle Report-/CSV-Dateien mitkopieren
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            if name.endswith(".html") or name.endswith(".csv"):
                shutil.copy2(os.path.join(output_dir, name), os.path.join(site_dir, name))

    # Startseite = neuester Report (sonst Platzhalter)
    index_path = os.path.join(site_dir, "index.html")
    if reports:
        shutil.copy2(os.path.join(output_dir, reports[0]), index_path)
        print(f"  Pages-Startseite = {reports[0]}")
    else:
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(_PLACEHOLDER)
        print("  Kein Report gefunden – Platzhalter-Startseite erzeugt.")

    return site_dir


if __name__ == "__main__":
    out = build()
    print(f"  Site erzeugt in: {os.path.abspath(out)}")
