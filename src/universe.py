"""
Liefert die Liste der S&P-500-Ticker.

Reihenfolge der Quellen:
1. Frischer Abruf der aktuellen Index-Mitglieder von Wikipedia (wird gecacht).
2. Lokaler Cache (output/sp500_tickers.csv) vom letzten erfolgreichen Abruf.
3. Fest eingebauter Minimal-Fallback (falls offline und kein Cache vorhanden).

Yahoo verwendet "-" statt "." in Tickern mit Aktienklassen (z. B. BRK-B), das
wird hier automatisch korrigiert.
"""
from __future__ import annotations

import io
import os
import datetime as _dt
import urllib.request

import pandas as pd

_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_CACHE_FILE = "sp500_tickers.csv"

# Minimaler Fallback (nur falls online-Abruf UND Cache fehlen).
_FALLBACK = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "TSLA", "JPM",
    "V", "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "AVGO", "CVX", "MRK",
]


def _normalize(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def _fetch_from_wikipedia() -> list[str]:
    # Wikipedia blockt Requests ohne User-Agent (HTTP 403). Daher HTML selbst
    # mit Browser-aehnlichem Header laden und an pandas.read_html uebergeben.
    req = urllib.request.Request(
        _WIKI_URL,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chartanalyse/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    # pandas.read_html benoetigt lxml; liest alle Tabellen der Seite.
    tables = pd.read_html(io.StringIO(html))
    df = tables[0]
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    tickers = [_normalize(str(s)) for s in df[col].tolist()]
    # Plausibilitaet: der S&P 500 hat ~500 Mitglieder.
    if len(tickers) < 400:
        raise ValueError(f"Unerwartet wenige Ticker von Wikipedia: {len(tickers)}")
    return tickers


def get_sp500_tickers(output_dir: str = "output", force_refresh: bool = False) -> list[str]:
    """Gibt die aktuelle S&P-500-Tickerliste zurueck (mit Caching + Fallback)."""
    os.makedirs(output_dir, exist_ok=True)
    cache_path = os.path.join(output_dir, _CACHE_FILE)

    if not force_refresh and os.path.exists(cache_path):
        try:
            cached = pd.read_csv(cache_path)
            tickers = [_normalize(t) for t in cached["ticker"].tolist()]
            if len(tickers) >= 400:
                return tickers
        except Exception:
            pass  # Cache defekt -> neu holen

    try:
        tickers = _fetch_from_wikipedia()
        pd.DataFrame(
            {"ticker": tickers, "fetched": _dt.date.today().isoformat()}
        ).to_csv(cache_path, index=False)
        return tickers
    except Exception as exc:  # offline o. Wikipedia-Struktur geaendert
        if os.path.exists(cache_path):
            cached = pd.read_csv(cache_path)
            return [_normalize(t) for t in cached["ticker"].tolist()]
        print(f"  ! Konnte S&P-500-Liste nicht laden ({exc}). Nutze Fallback-Liste.")
        return list(_FALLBACK)
