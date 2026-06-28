"""
Erzeugt die Ausgaben eines Laufs:
  - Konsolen-Zusammenfassung
  - CSV mit allen Alerts
  - selbst-erklaerendes HTML mit Chart je Alert (Linie + Umkehrkerze markiert)
"""
from __future__ import annotations

import base64
import io
import os
import datetime as _dt

import pandas as pd

from .reversal import Signal, EarlyWarning
from .levels import Level

# matplotlib ohne Display-Backend (laeuft headless / im Batch).
import logging
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Harmlose Font-Gewicht-Warnungen des Chart-Styles stummschalten.
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

try:
    import mplfinance as mpf
    _HAS_MPF = True
except Exception:
    _HAS_MPF = False


_KIND_LABEL = {
    "SUPPORT_BOUNCE": "Support-Bounce (bullisch)",
    "RESISTANCE_REJECT": "Resistance-Reject (baerisch)",
}
_SIDE_LABEL = {
    "SUPPORT": "an Support (Linie unter Kurs)",
    "RESISTANCE": "an Resistance (Linie über Kurs)",
}


def _chart_png_b64(ticker: str, df: pd.DataFrame, sig: Signal, levels: list[Level], cfg) -> str | None:
    """Rendert einen Candlestick-Chart als base64-PNG (oder None bei Fehler)."""
    try:
        plot_df = df.tail(cfg.CHART_LOOKBACK_BARS).copy()
        plot_df.index = pd.to_datetime(plot_df.index)

        # Nur Linien im sichtbaren Preisbereich einzeichnen.
        lo, hi = plot_df["Low"].min(), plot_df["High"].max()
        hlines = sorted({round(lv.price, 4) for lv in levels if lo <= lv.price <= hi})

        if _HAS_MPF:
            buf = io.BytesIO()
            mc = mpf.make_marketcolors(up="#16a34a", down="#dc2626", inherit=True)
            style = mpf.make_mpf_style(base_mpf_style="charles", marketcolors=mc, gridstyle=":")
            mpf.plot(
                plot_df,
                type="candle",
                style=style,
                volume=True,
                title=f"\n{ticker} – {_KIND_LABEL.get(sig.kind, sig.kind)}",
                hlines=dict(hlines=hlines, colors=["#9ca3af"] * len(hlines), linewidths=0.7, linestyle="--"),
                figsize=(10, 5.5),
                tight_layout=True,
                savefig=dict(fname=buf, dpi=110, bbox_inches="tight"),
            )
            plt.close("all")
            buf.seek(0)
            return base64.b64encode(buf.read()).decode("ascii")

        # Fallback ohne mplfinance: einfacher Linienchart.
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(plot_df.index, plot_df["Close"], color="#2563eb", lw=1.2)
        for y in hlines:
            ax.axhline(y, color="#9ca3af", ls="--", lw=0.7)
        ax.axhline(sig.level_price, color="#f59e0b", ls="-", lw=1.4, label="Signal-Linie")
        ax.set_title(f"{ticker} – {_KIND_LABEL.get(sig.kind, sig.kind)}")
        ax.legend(loc="best", fontsize=8)
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=110)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")
    except Exception as exc:
        print(f"  ! Chart fuer {ticker} fehlgeschlagen: {exc}")
        return None


def write_reports(
    signals: list[Signal],
    early: list[EarlyWarning],
    data: dict[str, pd.DataFrame],
    levels_by_ticker: dict[str, list[Level]],
    cfg,
    scanned: int,
) -> tuple[str | None, str | None, str | None]:
    """Schreibt Alerts-CSV, Fruehwarner-CSV und HTML.
    Rueckgabe: (alerts_csv, html, watch_csv)."""
    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    signals = sorted(signals, key=lambda s: s.confidence, reverse=True)
    early = sorted(early, key=lambda w: abs(w.distance_pct))

    # ---- CSV: bestaetigte Alerts ----
    rows = [
        {
            "ticker": s.ticker,
            "datum": s.date,
            "typ": s.kind,
            "richtung": s.direction,
            "linie": round(s.level_price, 2),
            "schluss": round(s.close, 2),
            "abstand_%": round(s.distance_pct, 2),
            "confidence": s.confidence,
            "linien_staerke": round(s.level_strength, 3),
            "kerzen_qualitaet": round(s.candle_quality, 3),
            "volumen_x": round(s.volume_ratio, 2),
        }
        for s in signals
    ]
    csv_path = os.path.join(cfg.OUTPUT_DIR, f"alerts_{stamp}.csv")
    pd.DataFrame(rows, columns=list(rows[0].keys()) if rows else
                 ["ticker", "datum", "typ", "richtung", "linie", "schluss",
                  "abstand_%", "confidence", "linien_staerke", "kerzen_qualitaet", "volumen_x"]
                 ).to_csv(csv_path, index=False)

    # ---- CSV: Fruehwarnungen ----
    watch_cols = ["ticker", "datum", "seite", "linie", "schluss",
                  "abstand_%", "linien_staerke", "beruehrungen"]
    watch_rows = [
        {
            "ticker": w.ticker, "datum": w.date, "seite": w.side,
            "linie": round(w.level_price, 2), "schluss": round(w.close, 2),
            "abstand_%": round(w.distance_pct, 2),
            "linien_staerke": round(w.level_strength, 3), "beruehrungen": w.touches,
        }
        for w in early
    ]
    watch_csv = os.path.join(cfg.OUTPUT_DIR, f"watchlist_{stamp}.csv")
    pd.DataFrame(watch_rows, columns=watch_cols).to_csv(watch_csv, index=False)

    # ---- HTML: Sektion 1 = bestaetigte Alerts (mit Charts) ----
    cards = []
    for s in signals:
        chart_html = ""
        if cfg.GENERATE_CHARTS and s.ticker in data:
            b64 = _chart_png_b64(s.ticker, data[s.ticker], s, levels_by_ticker.get(s.ticker, []), cfg)
            if b64:
                chart_html = f'<img class="chart" src="data:image/png;base64,{b64}" alt="{s.ticker}">'
        badge = "long" if s.direction == "LONG" else "short"
        cards.append(f"""
        <div class="card">
          <div class="head">
            <span class="ticker">{s.ticker}</span>
            <span class="badge {badge}">{_KIND_LABEL.get(s.kind, s.kind)}</span>
            <span class="conf">Confidence {s.confidence:.0f}</span>
          </div>
          <div class="meta">
            Datum {s.date} &middot; Linie {s.level_price:.2f} &middot; Schluss {s.close:.2f}
            ({s.distance_pct:+.2f} %) &middot; Volumen {s.volume_ratio:.2f}× &middot;
            Linien-Staerke {s.level_strength:.2f} &middot; Kerzen-Qualitaet {s.candle_quality:.2f}
          </div>
          {chart_html}
        </div>""")
    alerts_body = "\n".join(cards) if cards else (
        '<p class="empty">Heute keine bestaetigten Alerts oberhalb der Confidence-Schwelle '
        f'({cfg.CONFIDENCE_THRESHOLD}). Das ist normal – fundierte Umkehrsignale sind selten.</p>'
    )

    # ---- HTML: Sektion 2 = Fruehwarnungen (kompakte Tabelle) ----
    if early:
        wrows = "".join(
            "<tr>"
            f"<td class='tk'>{w.ticker}</td>"
            f"<td><span class='badge {'long' if w.side == 'SUPPORT' else 'short'}'>"
            f"{_SIDE_LABEL.get(w.side, w.side)}</span></td>"
            f"<td style='text-align:right'>{w.level_price:.2f}</td>"
            f"<td style='text-align:right'>{w.close:.2f}</td>"
            f"<td style='text-align:right'>{w.distance_pct:+.2f} %</td>"
            f"<td style='text-align:right'>{w.level_strength:.2f}</td>"
            f"<td style='text-align:right'>{w.touches}</td>"
            "</tr>"
            for w in early
        )
        watch_body = (
            "<table class='watch'><thead><tr>"
            "<th>Ticker</th><th>Lage</th><th>Linie</th><th>Schluss</th>"
            "<th>Abstand</th><th>Stärke</th><th>Ber.</th></tr></thead>"
            f"<tbody>{wrows}</tbody></table>"
        )
    else:
        watch_body = '<p class="empty">Aktuell keine Frühwarnungen (kein Kurs sitzt direkt an einer starken Linie).</p>'

    html_path = os.path.join(cfg.OUTPUT_DIR, f"alerts_{stamp}.html")
    html = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8">
<title>Chartanalyse Alerts {stamp}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background:#0f172a; color:#e2e8f0; }}
  header {{ padding: 24px 28px; border-bottom:1px solid #1e293b; }}
  header h1 {{ margin:0 0 6px; font-size:20px; }}
  header p {{ margin:0; color:#94a3b8; font-size:13px; }}
  .wrap {{ padding: 20px 28px; max-width: 1000px; margin: 0 auto; }}
  h2.sec {{ font-size:15px; margin:26px 0 12px; padding-bottom:6px; border-bottom:1px solid #1e293b; }}
  .card {{ background:#1e293b; border:1px solid #334155; border-radius:12px; padding:16px; margin-bottom:18px; }}
  .head {{ display:flex; align-items:center; gap:12px; flex-wrap:wrap; }}
  .ticker {{ font-size:18px; font-weight:700; }}
  .badge {{ font-size:12px; padding:3px 9px; border-radius:999px; font-weight:600; }}
  .badge.long {{ background:#064e3b; color:#6ee7b7; }}
  .badge.short {{ background:#7f1d1d; color:#fca5a5; }}
  .conf {{ margin-left:auto; font-weight:700; color:#fbbf24; }}
  .meta {{ color:#94a3b8; font-size:12.5px; margin:8px 0 12px; }}
  .chart {{ width:100%; border-radius:8px; background:#fff; }}
  .empty {{ color:#94a3b8; }}
  table.watch {{ width:100%; border-collapse:collapse; font-size:13px; }}
  table.watch th, table.watch td {{ padding:8px 10px; border-bottom:1px solid #1e293b; }}
  table.watch th {{ text-align:left; color:#94a3b8; font-weight:600; }}
  table.watch td.tk {{ font-weight:700; }}
  .disc {{ color:#64748b; font-size:11.5px; margin-top:24px; line-height:1.5; }}
</style></head>
<body>
<header>
  <h1>Chartanalyse – Support/Resistance</h1>
  <p>Lauf vom {_dt.datetime.now().strftime('%d.%m.%Y %H:%M')} &middot;
     {scanned} Aktien gescannt &middot; {len(signals)} bestätigte(r) Alert(s) &middot;
     {len(early)} Frühwarnung(en) &middot; Confidence-Schwelle {cfg.CONFIDENCE_THRESHOLD}</p>
</header>
<div class="wrap">
  <h2 class="sec">✅ Bestätigte Reversal-Alerts ({len(signals)})</h2>
  {alerts_body}
  <h2 class="sec">⚠️ Frühwarnungen – Kurs sitzt an starker Linie ({len(early)})</h2>
  {watch_body}
  <p class="disc">Hinweis: Heuristische Analyse historischer Kursdaten (Quelle: Yahoo Finance),
     keine Anlageberatung. Bestätigte Alerts brauchen eine Umkehrkerze; Frühwarnungen melden nur
     Nähe zur Linie (unsicherer, früher). Die Confidence ist ein technischer Score, keine Erfolgsgarantie.</p>
</div>
</body></html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return csv_path, html_path, watch_csv


def print_console_summary(signals: list[Signal], early: list[EarlyWarning], scanned: int, cfg) -> None:
    signals = sorted(signals, key=lambda s: s.confidence, reverse=True)
    early = sorted(early, key=lambda w: abs(w.distance_pct))
    print("\n" + "=" * 64)
    print(f"  ERGEBNIS: {scanned} Aktien gescannt, {len(signals)} bestaetigte(r) Alert(s) "
          f"(Conf >= {cfg.CONFIDENCE_THRESHOLD}), {len(early)} Fruehwarnung(en)")
    print("=" * 64)

    print(f"\n  BESTAETIGTE REVERSAL-ALERTS ({len(signals)}):")
    if not signals:
        print("    Keine. (Das ist normal – fundierte Umkehrsignale sind selten.)")
    else:
        print(f"    {'Ticker':<8} {'Richtung':<6} {'Typ':<20} {'Linie':>9} {'Conf':>6}")
        print("    " + "-" * 54)
        for s in signals:
            typ = "Support-Bounce" if s.kind == "SUPPORT_BOUNCE" else "Resistance-Reject"
            print(f"    {s.ticker:<8} {s.direction:<6} {typ:<20} {s.level_price:>9.2f} {s.confidence:>6.0f}")

    print(f"\n  FRUEHWARNUNGEN – Kurs sitzt an starker Linie ({len(early)}):")
    if not early:
        print("    Keine.")
    else:
        print(f"    {'Ticker':<8} {'Lage':<11} {'Linie':>9} {'Abstand':>9} {'Staerke':>8}")
        print("    " + "-" * 50)
        for w in early:
            lage = "Support" if w.side == "SUPPORT" else "Resistance"
            print(f"    {w.ticker:<8} {lage:<11} {w.level_price:>9.2f} {w.distance_pct:>+8.2f}% {w.level_strength:>8.2f}")
