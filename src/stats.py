"""
Liest die im Backtest ermittelten Umkehr-Quoten (backtest_rates.json) und
schlaegt fuer ein Signal die passende historische Quote nach (nach Seite &
Staerke-Klasse). Fehlt die Datei, wird einfach None zurueckgegeben.

Erzeugt wird backtest_rates.json von backtest.py.
"""
from __future__ import annotations

import json
import os

# Muss identisch zu den Klassen in backtest.py sein.
BUCKETS = [(0.0, 0.4), (0.4, 0.55), (0.55, 0.7), (0.7, 0.85), (0.85, 1.01)]

_RATES_FILE = "backtest_rates.json"


def bucket_label(strength: float) -> str:
    for lo, hi in BUCKETS:
        if lo <= strength < hi:
            return f"{lo:.2f}-{hi:.2f}" if hi <= 1.0 else f"{lo:.2f}-1.00"
    return "?"


def side_from_kind(kind: str) -> str:
    return "SUPPORT" if kind == "SUPPORT_BOUNCE" else "RESISTANCE"


def load_rates(path: str = _RATES_FILE) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def reversal_rate(rates: dict | None, side: str, strength: float) -> tuple[float, int] | None:
    """Liefert (quote 0..1, stichprobe n) fuer Seite+Staerke, sonst None.
    Faellt von (Seite+Klasse) -> (Seite gesamt) -> (gesamt) zurueck."""
    if not rates:
        return None
    b = bucket_label(strength)
    by_sb = rates.get("by_side_bucket", {}).get(side, {})
    cell = by_sb.get(b)
    if cell and cell.get("n") and cell.get("rate") is not None:
        return cell["rate"], cell["n"]
    sd = rates.get("by_side", {}).get(side)
    if sd and sd.get("n") and sd.get("rate") is not None:
        return sd["rate"], sd["n"]
    ov = rates.get("overall")
    if ov and ov.get("n") and ov.get("rate") is not None:
        return ov["rate"], ov["n"]
    return None


def format_rate(rates: dict | None, side: str, strength: float) -> str:
    """Kurzform fuer die Anzeige, z. B. '59 %' oder '–' wenn keine Daten."""
    r = reversal_rate(rates, side, strength)
    return f"{r[0] * 100:.0f} %" if r else "–"
