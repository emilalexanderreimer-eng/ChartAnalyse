"""
Laedt Tageskurse (OHLCV) ueber yfinance und liefert pro Ticker ein sauberes
DataFrame mit den Spalten: Open, High, Low, Close, Volume (Index = Datum).
Der Download erfolgt in Bloecken, um das Yahoo-API zu schonen.
"""
from __future__ import annotations

import pandas as pd
import yfinance as yf

_STD_COLS = ["Open", "High", "Low", "Close", "Volume"]


def _extract_single(raw: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Holt aus dem (ggf. MultiIndex-)Download das DataFrame eines Tickers."""
    if raw is None or raw.empty:
        return None

    if isinstance(raw.columns, pd.MultiIndex):
        # group_by="ticker" -> oberste Ebene ist der Ticker.
        if ticker not in raw.columns.get_level_values(0):
            return None
        df = raw[ticker].copy()
    else:
        df = raw.copy()

    missing = [c for c in _STD_COLS if c not in df.columns]
    if missing:
        return None

    df = df[_STD_COLS].dropna()
    df = df[df["Volume"] >= 0]
    return df if len(df) > 0 else None


def _chunks(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def download_history(
    tickers: list[str],
    period: str = "1y",
    interval: str = "1d",
    chunk_size: int = 50,
) -> dict[str, pd.DataFrame]:
    """Laedt die Historie aller Ticker. Rueckgabe: {ticker: DataFrame}."""
    result: dict[str, pd.DataFrame] = {}
    total = len(tickers)
    done = 0

    for chunk in _chunks(tickers, chunk_size):
        raw = yf.download(
            tickers=chunk,
            period=period,
            interval=interval,
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        for tkr in chunk:
            df = _extract_single(raw, tkr)
            if df is not None:
                result[tkr] = df
        done += len(chunk)
        print(f"  Daten geladen: {done}/{total} Ticker ...", flush=True)

    return result
