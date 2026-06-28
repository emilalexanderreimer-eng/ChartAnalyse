"""
Backtest: empirische Umkehr-Quote an Support/Resistance-Linien.

Beantwortet die Frage: Wenn der Kurs historisch eine starke Linie getestet hat,
wie oft kam danach eine UMKEHR (Reversal) statt eines AUSBRUCHS (Breakout)? –
aufgeschluesselt nach Linien-Staerke, Seite und Beruehrungen.

WICHTIG – kein Blick in die Zukunft (point-in-time):
  An jedem Test-Tag t werden die Linien NUR aus den Daten bis t gebildet
  (genauer: aus Pivots, die bis t bereits bestaetigt waren). Erst danach wird
  FORWARD Tage nach vorn geschaut, um den Ausgang zu klassifizieren.

Klassifikation eines Tests (Schlusskurs-basiert, erster Treffer zaehlt):
  Support  : REVERSAL  = Hoch steigt >= +MOVE% ueber den Test-Schluss
             BREAKOUT  = Schluss faellt unter Linie*(1-BREAK%)  (Linie bricht)
  Resistance: spiegelbildlich.
  Passiert keins davon in FORWARD Tagen -> "neutral" (zaehlt nicht in die Quote).

    python backtest.py                 # alle S&P-500, 3 Jahre  (dauert)
    python backtest.py --limit 100     # schneller: erste 100 Aktien
    python backtest.py --years 5 --forward 10 --move 3 --break 1.5
"""
from __future__ import annotations

import argparse
import bisect
import datetime as _dt
import os
import sys
import time

import pandas as pd

import config as cfg
from src.universe import get_sp500_tickers
from src.data import download_history
from src.levels import find_pivots, _cluster, _score_levels

# Staerke-Klassen fuer die Auswertung
_BUCKETS = [(0.0, 0.4), (0.4, 0.55), (0.55, 0.7), (0.7, 0.85), (0.85, 1.01)]


def _bucket_label(strength: float) -> str:
    for lo, hi in _BUCKETS:
        if lo <= strength < hi:
            return f"{lo:.2f}-{hi:.2f}" if hi <= 1.0 else f"{lo:.2f}-1.00"
    return "?"


def _evaluate_stock(df: pd.DataFrame, p) -> list[dict]:
    """Liefert pro Test-Ereignis ein dict mit staerke/seite/touches/outcome."""
    n = len(df)
    if n < p.lookback + p.forward + 5:
        return []

    lows = df["Low"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)

    # Pivots EINMAL fuer die gesamte Historie (point-in-time-Nutzung danach).
    p_high, p_low = find_pivots(df, cfg.PIVOT_LEFT, cfg.PIVOT_RIGHT)
    pivots = sorted(p_high + p_low, key=lambda x: x[0])  # (idx, preis)
    if not pivots:
        return []
    piv_idx = [i for i, _ in pivots]

    events: list[dict] = []
    right = cfg.PIVOT_RIGHT
    zone = cfg.TOUCH_ZONE
    pierce = cfg.PIERCE_TOLERANCE
    move = p.move
    brk = p.brk

    for t in range(p.lookback, n - p.forward):
        win_start = t - p.lookback
        # Pivots, die bis t bestaetigt sind (idx + right <= t) und im Fenster liegen
        lo_pos = bisect.bisect_left(piv_idx, win_start)
        hi_pos = bisect.bisect_right(piv_idx, t - right)
        avail = [(piv_idx[k] - win_start, pivots[k][1]) for k in range(lo_pos, hi_pos)]
        if len(avail) < cfg.MIN_TOUCHES:
            continue

        levels = _cluster(avail, cfg.LEVEL_TOLERANCE)
        levels = [lv for lv in levels if lv.touches >= cfg.MIN_TOUCHES]
        if not levels:
            continue
        _score_levels(levels, p.lookback)

        low_t, high_t, close_t = lows[t], highs[t], closes[t]
        prev_low, prev_high = lows[t - 1], highs[t - 1]

        for lv in levels:
            L = lv.price
            # ---- Support-Test: Linie unter/bei Kurs, Tief kommt herunter ----
            if L <= close_t:
                touched = (L * (1 - pierce)) <= low_t <= (L * (1 + zone))
                fresh = not ((L * (1 - pierce)) <= prev_low <= (L * (1 + zone)))
                if touched and fresh:
                    outcome = _classify_support(
                        highs, closes, t, p.forward, close_t, L, move, brk)
                    events.append({"side": "SUPPORT", "strength": lv.strength,
                                   "touches": lv.touches, "outcome": outcome})
            # ---- Resistance-Test: Linie ueber/bei Kurs, Hoch laeuft hinauf ----
            if L >= close_t:
                touched = (L * (1 - zone)) <= high_t <= (L * (1 + pierce))
                fresh = not ((L * (1 - zone)) <= prev_high <= (L * (1 + pierce)))
                if touched and fresh:
                    outcome = _classify_resistance(
                        lows, closes, t, p.forward, close_t, L, move, brk)
                    events.append({"side": "RESISTANCE", "strength": lv.strength,
                                   "touches": lv.touches, "outcome": outcome})
    return events


def _classify_support(highs, closes, t, forward, entry, L, move, brk):
    up_target = entry * (1 + move)
    break_level = L * (1 - brk)
    for k in range(t + 1, t + 1 + forward):
        if closes[k] < break_level:
            return "breakout"      # Support gebrochen (Abwaerts-Durchbruch)
        if highs[k] >= up_target:
            return "reversal"      # nach oben abgeprallt
    return "neutral"


def _classify_resistance(lows, closes, t, forward, entry, L, move, brk):
    down_target = entry * (1 - move)
    break_level = L * (1 + brk)
    for k in range(t + 1, t + 1 + forward):
        if closes[k] > break_level:
            return "breakout"      # Resistance gebrochen (Aufwaerts-Durchbruch)
        if lows[k] <= down_target:
            return "reversal"      # nach unten abgeprallt
    return "neutral"


def _aggregate(events: list[dict]) -> dict:
    """Gruppiert nach Staerke-Bucket: zaehlt reversal/breakout/neutral + Quote."""
    agg: dict[str, dict[str, int]] = {}
    for e in events:
        b = _bucket_label(e["strength"])
        d = agg.setdefault(b, {"reversal": 0, "breakout": 0, "neutral": 0})
        d[e["outcome"]] += 1
    return agg


def _rate(d: dict) -> float | None:
    decided = d["reversal"] + d["breakout"]
    return (d["reversal"] / decided) if decided else None


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Backtest der Umkehr-Quote an S/R-Linien")
    ap.add_argument("--limit", type=int, default=None, help="nur erste N Aktien")
    ap.add_argument("--tickers", type=str, default=None, help="eigene Ticker, kommagetrennt")
    ap.add_argument("--years", type=int, default=3, help="Historie in Jahren (Standard 3)")
    ap.add_argument("--lookback", type=int, default=252, help="Fenster fuer Linienbildung (Bars)")
    ap.add_argument("--forward", type=int, default=10, help="Beobachtungsfenster nach Test (Bars)")
    ap.add_argument("--move", type=float, default=3.0, help="Reversal-Bewegung in %% (Standard 3)")
    ap.add_argument("--break", dest="brk", type=float, default=1.5,
                    help="Linienbruch in %% (Standard 1.5)")
    return ap.parse_args(argv)


def main(argv) -> int:
    p = parse_args(argv)
    p.move /= 100.0
    p.brk /= 100.0

    t0 = time.time()
    print("=" * 64)
    print("  BACKTEST – Umkehr-Quote an Support/Resistance-Linien")
    print("=" * 64)

    if p.tickers:
        tickers = [t.strip().upper().replace(".", "-") for t in p.tickers.split(",") if t.strip()]
    else:
        print("  Lade S&P-500-Tickerliste ...")
        tickers = get_sp500_tickers(cfg.OUTPUT_DIR)
    if p.limit:
        tickers = tickers[: p.limit]
    print(f"  {len(tickers)} Aktien, {p.years} Jahre Historie, "
          f"Forward {p.forward}d, Move {p.move*100:.1f}%, Break {p.brk*100:.1f}%")

    print("\n  Lade Kursdaten ...")
    data = download_history(tickers, period=f"{p.years}y", interval="1d",
                            chunk_size=cfg.DOWNLOAD_CHUNK_SIZE)
    print(f"  Daten fuer {len(data)} Aktien.")

    print("\n  Werte historische Tests aus (point-in-time) ...")
    all_events: list[dict] = []
    for i, (tkr, df) in enumerate(data.items(), 1):
        try:
            all_events.extend(_evaluate_stock(df, p))
        except Exception as exc:
            print(f"  ! {tkr}: {exc}")
        if i % 50 == 0:
            print(f"    {i}/{len(data)} Aktien ...", flush=True)

    _report(all_events, p, scanned=len(data), elapsed=time.time() - t0)
    return 0


def _print_table(title, agg):
    print(f"\n  {title}")
    print(f"    {'Staerke':<12} {'Reversal':>9} {'Breakout':>9} {'neutral':>8} "
          f"{'Umkehr-Quote':>13} {'n(entsch.)':>11}")
    print("    " + "-" * 66)
    order = sorted(agg.keys())
    tot = {"reversal": 0, "breakout": 0, "neutral": 0}
    for b in order:
        d = agg[b]
        for k in tot:
            tot[k] += d[k]
        r = _rate(d)
        rate_s = f"{r*100:5.1f} %" if r is not None else "   – "
        print(f"    {b:<12} {d['reversal']:>9} {d['breakout']:>9} {d['neutral']:>8} "
              f"{rate_s:>13} {d['reversal']+d['breakout']:>11}")
    r = _rate(tot)
    rate_s = f"{r*100:5.1f} %" if r is not None else "   – "
    print("    " + "-" * 66)
    print(f"    {'GESAMT':<12} {tot['reversal']:>9} {tot['breakout']:>9} {tot['neutral']:>8} "
          f"{rate_s:>13} {tot['reversal']+tot['breakout']:>11}")


def _report(events, p, scanned, elapsed):
    print("\n" + "=" * 64)
    print(f"  ERGEBNIS: {len(events)} Test-Ereignisse aus {scanned} Aktien")
    print("=" * 64)
    if not events:
        print("  Keine Ereignisse gefunden.")
        return

    _print_table("NACH STAERKE (alle):", _aggregate(events))
    _print_table("NUR SUPPORT:", _aggregate([e for e in events if e["side"] == "SUPPORT"]))
    _print_table("NUR RESISTANCE:", _aggregate([e for e in events if e["side"] == "RESISTANCE"]))

    # CSV mit Rohdaten
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    csv_path = os.path.join(cfg.OUTPUT_DIR, f"backtest_{stamp}.csv")
    pd.DataFrame(events).to_csv(csv_path, index=False)
    print(f"\n  Rohdaten-CSV: {csv_path}")
    print(f"  Laufzeit: {elapsed:.1f} s")
    print("\n  Lies die 'Umkehr-Quote' so: Anteil der ENTSCHIEDENEN Tests, die "
          "abprallten\n  statt durchzubrechen. 50 % = Muenzwurf. Hoeher bei "
          "hoeherer Staerke = die\n  Linienstaerke hat Vorhersagewert. (Heuristik, keine Garantie.)")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
