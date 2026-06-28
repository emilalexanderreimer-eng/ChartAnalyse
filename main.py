"""
Chartanalyse – taeglicher Scan des S&P 500 auf fundierte Support/Resistance-
Reversal-Signale.

Start:
    python main.py                  # kompletter S&P-500-Scan
    python main.py --limit 30       # nur die ersten 30 (schneller Test)
    python main.py --tickers AAPL,MSFT,NVDA
    python main.py --refresh-universe   # S&P-500-Liste neu von Wikipedia holen
"""
from __future__ import annotations

import argparse
import sys
import time
import webbrowser

import config as cfg
from src.universe import get_sp500_tickers
from src.data import download_history
from src.analyze import analyze_ticker
from src.report import write_reports, print_console_summary
from src.notify import send_email


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S&P-500 Support/Resistance Reversal-Scanner")
    p.add_argument("--limit", type=int, default=None, help="nur die ersten N Ticker scannen")
    p.add_argument("--tickers", type=str, default=None, help="eigene Ticker, kommagetrennt")
    p.add_argument("--refresh-universe", action="store_true", help="S&P-500-Liste neu laden")
    p.add_argument("--threshold", type=float, default=None, help="Confidence-Schwelle ueberschreiben")
    p.add_argument("--no-charts", action="store_true", help="keine Charts erzeugen (schneller)")
    p.add_argument("--no-open", action="store_true", help="HTML-Report nicht automatisch oeffnen")
    p.add_argument("--email", action="store_true", help="bei Alerts E-Mail senden (email_config.json)")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.threshold is not None:
        cfg.CONFIDENCE_THRESHOLD = args.threshold
    if args.no_charts:
        cfg.GENERATE_CHARTS = False

    t0 = time.time()
    print("=" * 64)
    print("  CHARTANALYSE – S&P 500 Support/Resistance Reversal-Scanner")
    print("=" * 64)

    # 1) Ticker-Universum bestimmen
    if args.tickers:
        tickers = [t.strip().upper().replace(".", "-") for t in args.tickers.split(",") if t.strip()]
        print(f"  Eigene Ticker-Liste: {len(tickers)} Werte")
    else:
        print("  Lade S&P-500-Tickerliste ...")
        tickers = get_sp500_tickers(cfg.OUTPUT_DIR, force_refresh=args.refresh_universe)
        print(f"  {len(tickers)} Ticker im Universum.")
    if args.limit:
        tickers = tickers[: args.limit]
        print(f"  Begrenzt auf die ersten {len(tickers)} Ticker.")

    # 2) Kursdaten laden
    print("\n  Lade Kursdaten von Yahoo Finance ...")
    data = download_history(
        tickers,
        period=cfg.HISTORY_PERIOD,
        interval=cfg.INTERVAL,
        chunk_size=cfg.DOWNLOAD_CHUNK_SIZE,
    )
    print(f"  Daten fuer {len(data)}/{len(tickers)} Ticker erhalten.")
    if not data:
        print("  ! Keine Daten geladen (Internetverbindung?). Abbruch.")
        return 1

    # 3) Analyse
    print("\n  Analysiere Linien, Umkehrsignale & Fruehwarnungen ...")
    signals = []
    early_warnings = []
    levels_by_ticker = {}
    for tkr, df in data.items():
        try:
            sig, warns, levels = analyze_ticker(tkr, df, cfg)
            levels_by_ticker[tkr] = levels
            if sig is not None:
                signals.append(sig)          # bestaetigter Reversal hat Vorrang
            else:
                early_warnings.extend(warns)  # sonst ggf. Fruehwarnung
        except Exception as exc:
            print(f"  ! Analyse von {tkr} fehlgeschlagen: {exc}")

    # 4) Ausgabe
    print_console_summary(signals, early_warnings, scanned=len(data), cfg=cfg)
    csv_path, html_path, watch_csv = write_reports(
        signals, early_warnings, data, levels_by_ticker, cfg, scanned=len(data)
    )
    print(f"\n  CSV (Alerts)      : {csv_path}")
    print(f"  CSV (Fruehwarner) : {watch_csv}")
    print(f"  HTML              : {html_path}")
    print(f"  Laufzeit: {time.time() - t0:.1f} s")

    # 5) Optional: E-Mail-Benachrichtigung
    if args.email:
        send_email(signals, early_warnings, html_path, cfg)

    if html_path and cfg.OPEN_HTML_WHEN_DONE and not args.no_open:
        try:
            webbrowser.open("file://" + __import__("os").path.abspath(html_path))
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
