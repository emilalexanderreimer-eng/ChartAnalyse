"""
Erkennt Support-/Resistance-Linien aus Tageskursen.

Vorgehen:
1. Swing-Pivots finden  (lokale Hochs/Tiefs in einem Fenster).
2. Pivots zu Zonen clustern (nahe beieinander liegende Pivots = eine Linie).
3. Jede Zone bewerten (Staerke = Anzahl Beruehrungen + Aktualitaet).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Level:
    price: float                 # Preis der Linie (Mittel der Pivots)
    touches: int                 # Anzahl beruehrender Swing-Punkte
    first_idx: int               # Index der ersten Beruehrung
    last_idx: int                # Index der juengsten Beruehrung
    member_prices: list[float] = field(default_factory=list)
    strength: float = 0.0        # 0..1, gesamte Linienstaerke


def find_pivots(
    df: pd.DataFrame, left: int, right: int
) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Liefert (pivot_highs, pivot_lows) als Liste von (index, preis)."""
    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()
    n = len(df)
    pivot_highs: list[tuple[int, float]] = []
    pivot_lows: list[tuple[int, float]] = []

    for i in range(left, n - right):
        win_h = highs[i - left : i + right + 1]
        if highs[i] >= win_h.max():
            pivot_highs.append((i, float(highs[i])))
        win_l = lows[i - left : i + right + 1]
        if lows[i] <= win_l.min():
            pivot_lows.append((i, float(lows[i])))

    return pivot_highs, pivot_lows


def _cluster(pivots: list[tuple[int, float]], tol: float) -> list[Level]:
    """Fasst preislich nahe Pivots zu Zonen zusammen (1D-Clustering)."""
    if not pivots:
        return []

    # Nach Preis sortieren, dann benachbarte innerhalb der Toleranz mergen.
    pivots_sorted = sorted(pivots, key=lambda p: p[1])
    clusters: list[list[tuple[int, float]]] = [[pivots_sorted[0]]]

    for idx, price in pivots_sorted[1:]:
        ref = np.mean([p for _, p in clusters[-1]])
        if abs(price - ref) <= tol * ref:
            clusters[-1].append((idx, price))
        else:
            clusters.append([(idx, price)])

    levels: list[Level] = []
    for cl in clusters:
        prices = [p for _, p in cl]
        idxs = [i for i, _ in cl]
        levels.append(
            Level(
                price=float(np.mean(prices)),
                touches=len(cl),
                first_idx=min(idxs),
                last_idx=max(idxs),
                member_prices=prices,
            )
        )
    return levels


def _score_levels(levels: list[Level], n_bars: int) -> None:
    """Setzt level.strength (0..1) aus Beruehrungszahl und Aktualitaet."""
    if not levels:
        return
    max_touches = max(lv.touches for lv in levels)
    for lv in levels:
        # Mehr Beruehrungen -> staerker (gedeckelt am Maximum dieser Aktie).
        touch_score = lv.touches / max_touches if max_touches else 0.0
        # Juengere letzte Beruehrung -> relevanter.
        recency_score = lv.last_idx / (n_bars - 1) if n_bars > 1 else 0.0
        lv.strength = float(0.65 * touch_score + 0.35 * recency_score)


def build_levels(
    df: pd.DataFrame,
    left: int,
    right: int,
    tol: float,
    min_touches: int,
) -> list[Level]:
    """Komplette Pipeline: Pivots -> Cluster -> Bewertung -> Filter."""
    p_high, p_low = find_pivots(df, left, right)
    # Hochs und Tiefs gemeinsam clustern: eine Linie kann beide Rollen spielen
    # (alte Resistance wird zu neuer Support und umgekehrt).
    all_pivots = p_high + p_low
    levels = _cluster(all_pivots, tol)
    levels = [lv for lv in levels if lv.touches >= min_touches]
    _score_levels(levels, len(df))
    levels.sort(key=lambda lv: lv.price)
    return levels
