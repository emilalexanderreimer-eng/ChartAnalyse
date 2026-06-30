"""
Erkennt eine bestaetigte Umkehr an einer Support-/Resistance-Linie.

Ein Alert entsteht NUR, wenn die letzte (abgeschlossene) Kerze:
  - eine starke Linie tatsaechlich beruehrt/durchsticht und
  - dort eine klare Umkehr-Kerze bildet (langer Ablehnungs-Docht, Schluss
    zurueck auf der "richtigen" Seite der Linie) und
  - moeglichst mit Volumenbestaetigung.

Daraus wird ein Confidence-Score (0..100) berechnet; nur Werte oberhalb der
Schwelle werden als Signal zurueckgegeben.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .levels import Level


@dataclass
class Signal:
    ticker: str
    kind: str            # "SUPPORT_BOUNCE" oder "RESISTANCE_REJECT"
    direction: str       # "LONG" (bullisch) oder "SHORT" (baerisch)
    level_price: float
    close: float
    confidence: float    # 0..100
    level_strength: float
    candle_quality: float
    volume_ratio: float
    date: str
    distance_pct: float  # Abstand Schluss <-> Linie in %


@dataclass
class EarlyWarning:
    """Fruehwarnung: Trend (DEMA+SuperTrend) laeuft auf eine S/R-Linie zu, die
    moeglicherweise durchbrochen wird.
      direction='LONG'  -> bullish, Kurs naehert sich RESISTANCE von unten
      direction='SHORT' -> bearish, Kurs naehert sich SUPPORT von oben
    """
    ticker: str
    side: str            # "SUPPORT" oder "RESISTANCE" (welche Linie)
    direction: str       # "LONG" oder "SHORT" (Trend-Richtung)
    level_price: float
    close: float
    distance_pct: float  # signiert: <0 = Linie ueber Kurs, >0 = Linie unter Kurs
    level_strength: float
    touches: int
    date: str


def _candle_metrics(bar: pd.Series) -> dict:
    o, h, l, c = (
        float(bar["Open"]),
        float(bar["High"]),
        float(bar["Low"]),
        float(bar["Close"]),
    )
    rng = h - l
    body = abs(c - o)
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)
    return {
        "open": o, "high": h, "low": l, "close": c,
        "range": rng, "body": body,
        "lower_wick": lower_wick, "upper_wick": upper_wick,
    }


def _volume_ratio(df: pd.DataFrame, window: int = 20) -> float:
    vols = df["Volume"].to_numpy(dtype=float)
    if len(vols) < 2:
        return 1.0
    ref = vols[-(window + 1) : -1]
    avg = ref.mean() if len(ref) else vols[:-1].mean()
    if not np.isfinite(avg) or avg <= 0:
        return 1.0
    return float(vols[-1] / avg)


def detect_signal(ticker: str, df: pd.DataFrame, levels: list[Level], cfg) -> Signal | None:
    """Prueft die letzte Kerze gegen alle Linien; gibt das beste Signal zurueck."""
    if len(df) < max(cfg.PIVOT_LEFT + cfg.PIVOT_RIGHT + 2, 25) or not levels:
        return None

    last = df.iloc[-1]
    m = _candle_metrics(last)
    if m["range"] <= 0:
        return None

    vol_ratio = _volume_ratio(df)
    date_str = str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1])

    prior_low = float(df.iloc[-2]["Low"]) if len(df) >= 2 else m["low"]
    prior_high = float(df.iloc[-2]["High"]) if len(df) >= 2 else m["high"]

    best: Signal | None = None

    for lv in levels:
        price = lv.price
        zone_up = price * (1 + cfg.TOUCH_ZONE)
        zone_dn = price * (1 - cfg.TOUCH_ZONE)
        pierce_dn = price * (1 - cfg.PIERCE_TOLERANCE)
        pierce_up = price * (1 + cfg.PIERCE_TOLERANCE)

        # ---- Support-Bounce (bullisch): Tief testet Linie, Schluss drueber ----
        touched_support = pierce_dn <= m["low"] <= zone_up
        closed_above = m["close"] > price
        bullish = m["close"] >= m["open"]
        lower_wick_ratio = m["lower_wick"] / m["range"]
        if touched_support and closed_above and bullish and lower_wick_ratio >= cfg.MIN_WICK_RATIO:
            if cfg.REQUIRE_PRIOR_TOUCH and not (prior_low <= zone_up):
                pass
            else:
                cq = _candle_quality(lower_wick_ratio, m, price, "LONG")
                conf = _confidence(lv.strength, cq, vol_ratio, cfg)
                if vol_ratio >= cfg.MIN_VOLUME_RATIO and conf >= cfg.CONFIDENCE_THRESHOLD:
                    sig = Signal(
                        ticker=ticker, kind="SUPPORT_BOUNCE", direction="LONG",
                        level_price=price, close=m["close"], confidence=conf,
                        level_strength=lv.strength, candle_quality=cq,
                        volume_ratio=vol_ratio, date=date_str,
                        distance_pct=(m["close"] - price) / price * 100,
                    )
                    if best is None or sig.confidence > best.confidence:
                        best = sig

        # ---- Resistance-Reject (baerisch): Hoch testet Linie, Schluss drunter ----
        touched_resist = zone_dn <= m["high"] <= pierce_up
        closed_below = m["close"] < price
        bearish = m["close"] <= m["open"]
        upper_wick_ratio = m["upper_wick"] / m["range"]
        if touched_resist and closed_below and bearish and upper_wick_ratio >= cfg.MIN_WICK_RATIO:
            if cfg.REQUIRE_PRIOR_TOUCH and not (prior_high >= zone_dn):
                pass
            else:
                cq = _candle_quality(upper_wick_ratio, m, price, "SHORT")
                conf = _confidence(lv.strength, cq, vol_ratio, cfg)
                if vol_ratio >= cfg.MIN_VOLUME_RATIO and conf >= cfg.CONFIDENCE_THRESHOLD:
                    sig = Signal(
                        ticker=ticker, kind="RESISTANCE_REJECT", direction="SHORT",
                        level_price=price, close=m["close"], confidence=conf,
                        level_strength=lv.strength, candle_quality=cq,
                        volume_ratio=vol_ratio, date=date_str,
                        distance_pct=(m["close"] - price) / price * 100,
                    )
                    if best is None or sig.confidence > best.confidence:
                        best = sig

    return best


def detect_early_warnings(ticker: str, df: pd.DataFrame, levels: list[Level], cfg) -> list[EarlyWarning]:
    """Fruehwarnung: DEMA+SuperTrend zeigen in dieselbe Richtung UND der Kurs
    laeuft gerade auf eine S/R-Linie zu, die in dieser Richtung durchbrochen
    werden koennte.

    Bullish (Kurs > DEMA(200), SuperTrend gruen):
      -> warnt bei RESISTANCE-Linien in der Naehe (Ausbruch nach oben moeglich)
    Bearish (Kurs < DEMA(200), SuperTrend rot):
      -> warnt bei SUPPORT-Linien in der Naehe (Ausbruch nach unten moeglich)
    Wenn DEMA und SuperTrend in verschiedene Richtungen zeigen: keine Warnung.
    """
    if not getattr(cfg, "EARLY_WARNING_ENABLED", True) or not levels or len(df) < 2:
        return []

    from .indicators import dema as _dema, supertrend as _supertrend

    close = float(df.iloc[-1]["Close"])
    prior_close = float(df.iloc[-2]["Close"])
    if close <= 0:
        return []

    # ---- DEMA + SuperTrend bestimmen ----
    dema_period = getattr(cfg, "DEMA_PERIOD", 200)
    st_period = getattr(cfg, "ST_ATR_PERIOD", 12)
    st_mult = getattr(cfg, "ST_MULTIPLIER", 3.0)

    try:
        dema_val = float(_dema(df["Close"], dema_period).iloc[-1])
        st_dir, _ = _supertrend(df, st_period, st_mult)
        st_bullish = int(st_dir.iloc[-1]) == 1
    except Exception:
        return []

    if not np.isfinite(dema_val):
        return []  # nicht genug Daten fuer DEMA

    above_dema = close > dema_val

    if above_dema and st_bullish:
        direction = "LONG"
        wanted_side = "RESISTANCE"   # Ausbruch nach oben ueber Widerstand
    elif not above_dema and not st_bullish:
        direction = "SHORT"
        wanted_side = "SUPPORT"      # Ausbruch nach unten unter Support
    else:
        return []   # DEMA und SuperTrend widersprechen sich -> keine Warnung

    date_str = str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1])
    zone = cfg.EARLY_WARNING_ZONE
    only_fresh = getattr(cfg, "EARLY_WARNING_ONLY_FRESH", True)

    candidates: list[EarlyWarning] = []
    for lv in levels:
        if lv.strength < cfg.EARLY_WARNING_MIN_STRENGTH:
            continue
        dist = (close - lv.price) / lv.price
        if abs(dist) > zone:
            continue
        side = "RESISTANCE" if lv.price >= close else "SUPPORT"
        if side != wanted_side:
            continue
        if only_fresh and abs((prior_close - lv.price) / lv.price) <= zone:
            continue
        candidates.append(EarlyWarning(
            ticker=ticker, side=side, direction=direction,
            level_price=lv.price, close=close,
            distance_pct=dist * 100, level_strength=lv.strength,
            touches=lv.touches, date=date_str,
        ))

    if not candidates:
        return []
    candidates.sort(key=lambda w: abs(w.distance_pct))
    return candidates[:1]


def _candle_quality(wick_ratio: float, m: dict, price: float, direction: str) -> float:
    """0..1: wie ueberzeugend die Umkehrkerze ist."""
    # 1) Docht-Anteil (Rejection). 0.45 -> 0, 0.8+ -> 1.
    wick_comp = np.clip((wick_ratio - 0.45) / (0.80 - 0.45), 0, 1)
    # 2) Wo schliesst die Kerze in ihrer Spanne (nahe Hoch=bullisch / Tief=baerisch).
    if m["range"] > 0:
        close_pos = (m["close"] - m["low"]) / m["range"]  # 0=am Tief, 1=am Hoch
    else:
        close_pos = 0.5
    body_comp = close_pos if direction == "LONG" else (1 - close_pos)
    # 3) Wie deutlich der Schluss die Linie zurueckerobert hat.
    reclaim = min(abs(m["close"] - price) / price / 0.01, 1.0)  # 1 % => voll
    return float(np.clip(0.5 * wick_comp + 0.35 * body_comp + 0.15 * reclaim, 0, 1))


def _confidence(level_strength: float, candle_quality: float, vol_ratio: float, cfg) -> float:
    vol_comp = float(np.clip((vol_ratio - 1.0) / 1.0, 0, 1))  # 2x Volumen => voll
    score = (
        cfg.W_LEVEL_STRENGTH * level_strength
        + cfg.W_CANDLE_QUALITY * candle_quality
        + cfg.W_VOLUME * vol_comp
    )
    return round(score * 100, 1)
