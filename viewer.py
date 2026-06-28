"""
Lokaler Report-Viewer fuer die Chartanalyse.

Startet einen kleinen Webserver (nur Python-Standardbibliothek, keine extra
Pakete), der den output/-Ordner im Browser durchsuchbar macht: alle erzeugten
HTML-Reports (neueste zuerst) inklusive Charts, plus CSV-Download.

    python viewer.py                # http://localhost:8000
    python viewer.py --port 8080    # anderer Port
    python viewer.py --no-open      # Browser nicht automatisch oeffnen

Beenden mit Strg+C.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import config as cfg

# Dateinamen wie alerts_2026-06-28_1751.html
_STAMP_RE = re.compile(r"^alerts_(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})\.html$")


def _list_reports(output_dir: str) -> list[tuple[str, str]]:
    """(dateiname, lesbarer_zeitstempel), neueste zuerst."""
    items: list[tuple[str, str]] = []
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            m = _STAMP_RE.match(name)
            if m:
                items.append((name, f"{m.group(1)} {m.group(2)}:{m.group(3)} Uhr"))
    items.sort(reverse=True)  # Dateiname ist chronologisch sortierbar
    return items


def _index_html(output_dir: str) -> str:
    reports = _list_reports(output_dir)
    rows = []
    for name, when in reports:
        csv_name = name[:-5] + ".csv"
        csv_link = (
            f' <a class="csv" href="/{html.escape(csv_name)}">CSV</a>'
            if os.path.exists(os.path.join(output_dir, csv_name)) else ""
        )
        rows.append(
            f'<li><a class="rep" href="/{html.escape(name)}">{html.escape(when)}</a>{csv_link}</li>'
        )
    body = (
        "<ul class=list>" + "\n".join(rows) + "</ul>"
        if rows else
        '<p class=empty>Noch keine Reports vorhanden. Starte einen Scan mit '
        '<code>python main.py</code> – danach diese Seite neu laden.</p>'
    )
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chartanalyse – Reports</title>
<style>
  body {{ font-family:-apple-system,Segoe UI,Roboto,sans-serif; margin:0; background:#0f172a; color:#e2e8f0; }}
  header {{ padding:24px 28px; border-bottom:1px solid #1e293b; }}
  header h1 {{ margin:0 0 6px; font-size:20px; }}
  header p {{ margin:0; color:#94a3b8; font-size:13px; }}
  header code {{ color:#cbd5e1; }}
  .wrap {{ padding:20px 28px; max-width:760px; margin:0 auto; }}
  .list {{ list-style:none; padding:0; margin:0; }}
  .list li {{ background:#1e293b; border:1px solid #334155; border-radius:10px;
             padding:14px 16px; margin-bottom:10px; display:flex; align-items:center; gap:14px; }}
  a.rep {{ color:#93c5fd; font-weight:600; text-decoration:none; font-size:15px; }}
  a.rep:hover {{ text-decoration:underline; }}
  a.csv {{ margin-left:auto; color:#94a3b8; font-size:12px; border:1px solid #475569;
           border-radius:999px; padding:3px 10px; text-decoration:none; }}
  a.csv:hover {{ color:#e2e8f0; border-color:#94a3b8; }}
  .empty {{ color:#94a3b8; }}
  code {{ background:#1e293b; padding:2px 6px; border-radius:6px; }}
</style></head>
<body>
<header>
  <h1>Chartanalyse – Reports</h1>
  <p>{len(reports)} Report(s) im Ordner <code>{html.escape(os.path.abspath(output_dir))}</code></p>
</header>
<div class="wrap">{body}</div>
</body></html>"""


class _Handler(SimpleHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            payload = _index_html(self.directory).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def log_message(self, *args):  # ruhig bleiben
        pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Lokaler Report-Viewer fuer die Chartanalyse")
    ap.add_argument("--port", type=int, default=8000, help="Port (Standard 8000)")
    ap.add_argument("--no-open", action="store_true", help="Browser nicht automatisch oeffnen")
    args = ap.parse_args(argv)

    output_dir = os.path.abspath(cfg.OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)

    handler = partial(_Handler, directory=output_dir)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as exc:
        print(f"Konnte Port {args.port} nicht oeffnen ({exc}). "
              f"Anderen Port versuchen: python viewer.py --port 8080")
        return 1

    url = f"http://localhost:{args.port}/"
    print(f"Report-Viewer laeuft auf {url}")
    print("Beenden mit Strg+C.")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nViewer beendet.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
