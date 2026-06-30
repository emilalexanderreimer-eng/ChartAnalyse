"""
Technische Indikatoren fuer den DEMA+SuperTrend-Strategie-Filter.

Berechnet auf Tageskerzen (Tagesdaten). Beide Indikatoren entsprechen exakt
den Einstellungen aus dem TradingLab-Video:
  DEMA  : Laenge 200
  SuperTrend: ATR-Periode 12, Multiplikator 3
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def dema(series: pd.Series, period: int = 200) -> pd.Series:
    """Double Exponential Moving Average: 2*EMA(n) - EMA(EMA(n))."""
    ema1 = series.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    return 2 * ema1 - ema2


def supertrend(
    df: pd.DataFrame, period: int = 12, multiplier: float = 3.0
) -> tuple[pd.Series, pd.Series]:
    """
    Berechnet den SuperTrend-Indikator.

    Rueckgabe: (direction, line)
      direction: pd.Series mit +1 (bullish/gruen) oder -1 (bearish/rot)
      line     : pd.Series mit dem aktuellen SuperTrend-Wert (unteres oder oberes Band)
    """
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)
    n = len(df)

    # True Range
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # ATR (einfacher gleitender Durchschnitt ueber `period` Bars)
    atr = np.full(n, np.nan)
    for i in range(period - 1, n):
        atr[i] = np.mean(tr[i - period + 1 : i + 1])

    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    direction = np.ones(n, dtype=int)

    for i in range(1, n):
        if np.isnan(atr[i]) or np.isnan(atr[i - 1]):
            direction[i] = direction[i - 1]
            continue

        # Finales oberes Band
        if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Finales unteres Band
        if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Richtung
        prev = direction[i - 1]
        if prev == 1 and close[i] < final_lower[i]:
            direction[i] = -1
        elif prev == -1 and close[i] > final_upper[i]:
            direction[i] = 1
        else:
            direction[i] = prev

    st_line = np.where(direction == 1, final_lower, final_upper)
    return (
        pd.Series(direction, index=df.index, dtype=int),
        pd.Series(st_line, index=df.index, dtype=float),
    )
