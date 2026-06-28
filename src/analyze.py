"""
Verbindet Linienerkennung und Umkehr-Pruefung pro Aktie.
"""
from __future__ import annotations

import pandas as pd

from .levels import build_levels, Level
from .reversal import detect_signal, detect_early_warnings, Signal, EarlyWarning


def analyze_ticker(
    ticker: str, df: pd.DataFrame, cfg
) -> tuple[Signal | None, list[EarlyWarning], list[Level]]:
    """Analysiert eine Aktie.

    Rueckgabe: (bestaetigtes Signal oder None, Fruehwarnungen, alle Linien).
    """
    if df is None or len(df) < 30:
        return None, [], []

    levels = build_levels(
        df,
        left=cfg.PIVOT_LEFT,
        right=cfg.PIVOT_RIGHT,
        tol=cfg.LEVEL_TOLERANCE,
        min_touches=cfg.MIN_TOUCHES,
    )
    signal = detect_signal(ticker, df, levels, cfg)
    early = detect_early_warnings(ticker, df, levels, cfg)
    return signal, early, levels
