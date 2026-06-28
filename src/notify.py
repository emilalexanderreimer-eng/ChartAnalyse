"""
E-Mail-Benachrichtigung bei Alerts.

Liest die Zugangsdaten aus email_config.json (nicht im Code/Repo). Baut eine
HTML-Mail mit einer Alert-Tabelle und haengt den vollstaendigen HTML-Report
(inkl. Charts) an. Versand via SMTP + STARTTLS (Gmail: smtp.gmail.com:587,
App-Passwort noetig).
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage

from .reversal import Signal, EarlyWarning

_REQUIRED = ["sender_email", "app_password", "recipient_email", "smtp_host", "smtp_port"]
_KIND_LABEL = {
    "SUPPORT_BOUNCE": "Support-Bounce (bullisch)",
    "RESISTANCE_REJECT": "Resistance-Reject (baerisch)",
}
_SIDE_LABEL = {
    "SUPPORT": "an Support (Linie unter Kurs)",
    "RESISTANCE": "an Resistance (Linie über Kurs)",
}


def _valid(data: dict | None) -> dict | None:
    """Prueft, ob alle Pflichtfelder gesetzt und kein Platzhalter mehr drin ist."""
    if not data:
        return None
    if any(not str(data.get(k, "")).strip() for k in _REQUIRED):
        return None
    if "DEIN" in str(data["app_password"]).upper():
        return None
    return data


def _from_file(cfg) -> dict | None:
    path = cfg.EMAIL_CONFIG_FILE
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _from_env() -> dict | None:
    """Liest die Konfig aus Umgebungsvariablen (z. B. GitHub-Actions-Secrets)."""
    sender = os.environ.get("CHARTANALYSE_SENDER_EMAIL", "")
    if not sender:
        return None
    return {
        "sender_email": sender,
        "app_password": os.environ.get("CHARTANALYSE_APP_PASSWORD", ""),
        "recipient_email": os.environ.get("CHARTANALYSE_RECIPIENT_EMAIL", sender),
        "smtp_host": os.environ.get("CHARTANALYSE_SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": os.environ.get("CHARTANALYSE_SMTP_PORT", "587"),
    }


def load_email_config(cfg) -> dict | None:
    """Zugangsdaten laden: zuerst email_config.json, sonst Umgebungsvariablen
    (fuer die Cloud). Gibt None zurueck, wenn nichts Brauchbares vorliegt."""
    return _valid(_from_file(cfg)) or _valid(_from_env())


def _build_message(
    signals: list[Signal], early: list[EarlyWarning], ec: dict, attach_path: str | None
) -> EmailMessage:
    signals = sorted(signals, key=lambda s: s.confidence, reverse=True)
    early = sorted(early, key=lambda w: abs(w.distance_pct))
    n, ne = len(signals), len(early)
    msg = EmailMessage()
    parts = []
    if n:
        parts.append(f"{n} Alert(s)")
    if ne:
        parts.append(f"{ne} Frühwarnung(en)")
    msg["Subject"] = "Chartanalyse: " + (", ".join(parts) if parts else "keine Treffer")
    msg["From"] = ec["sender_email"]
    msg["To"] = ec["recipient_email"]

    # ---- Plaintext (Fallback) ----
    lines = [f"BESTAETIGTE ALERTS ({n}):", ""]
    for s in signals:
        lines.append(
            f"  {s.ticker:<6} {s.direction:<5} {_KIND_LABEL.get(s.kind, s.kind):<26} "
            f"Linie {s.level_price:.2f}  Conf {s.confidence:.0f}"
        )
    if not signals:
        lines.append("  keine")
    lines += ["", f"FRUEHWARNUNGEN ({ne}) – Kurs sitzt an starker Linie:", ""]
    for w in early:
        lines.append(
            f"  {w.ticker:<6} {('Support' if w.side == 'SUPPORT' else 'Resistance'):<11} "
            f"Linie {w.level_price:.2f}  Abstand {w.distance_pct:+.2f}%  Staerke {w.level_strength:.2f}"
        )
    if not early:
        lines.append("  keine")
    lines += ["", "Details + Charts: siehe angehaengten HTML-Report.",
              "Heuristische Analyse, keine Anlageberatung."]
    msg.set_content("\n".join(lines))

    # ---- HTML ----
    alert_rows = "".join(
        f"<tr>"
        f"<td style='font-weight:700'>{s.ticker}</td>"
        f"<td>{'LONG' if s.direction == 'LONG' else 'SHORT'}</td>"
        f"<td>{_KIND_LABEL.get(s.kind, s.kind)}</td>"
        f"<td style='text-align:right'>{s.level_price:.2f}</td>"
        f"<td style='text-align:right'>{s.close:.2f}</td>"
        f"<td style='text-align:right'>{s.volume_ratio:.2f}×</td>"
        f"<td style='text-align:right;font-weight:700;color:#b45309'>{s.confidence:.0f}</td>"
        f"</tr>"
        for s in signals
    )
    alert_table = (
        "<table cellspacing='0' cellpadding='6' "
        "style='border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;font-size:13px'>"
        "<thead><tr style='background:#f1f5f9;text-align:left'>"
        "<th>Ticker</th><th>Richtung</th><th>Typ</th><th>Linie</th><th>Schluss</th>"
        "<th>Vol</th><th>Conf</th></tr></thead>"
        f"<tbody>{alert_rows}</tbody></table>"
        if signals else "<p style='color:#64748b'>Keine bestätigten Alerts.</p>"
    )

    watch_rows = "".join(
        f"<tr>"
        f"<td style='font-weight:700'>{w.ticker}</td>"
        f"<td>{_SIDE_LABEL.get(w.side, w.side)}</td>"
        f"<td style='text-align:right'>{w.level_price:.2f}</td>"
        f"<td style='text-align:right'>{w.close:.2f}</td>"
        f"<td style='text-align:right'>{w.distance_pct:+.2f} %</td>"
        f"<td style='text-align:right'>{w.level_strength:.2f}</td>"
        f"</tr>"
        for w in early
    )
    watch_table = (
        "<table cellspacing='0' cellpadding='6' "
        "style='border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;font-size:13px'>"
        "<thead><tr style='background:#f1f5f9;text-align:left'>"
        "<th>Ticker</th><th>Lage</th><th>Linie</th><th>Schluss</th>"
        "<th>Abstand</th><th>Stärke</th></tr></thead>"
        f"<tbody>{watch_rows}</tbody></table>"
        if early else "<p style='color:#64748b'>Keine Frühwarnungen.</p>"
    )

    html = (
        "<div style='font-family:Segoe UI,Arial,sans-serif;color:#0f172a'>"
        f"<h2 style='margin:0 0 8px'>✅ Bestätigte Reversal-Alerts ({n})</h2>"
        f"{alert_table}"
        f"<h2 style='margin:22px 0 8px'>⚠️ Frühwarnungen – Kurs sitzt an starker Linie ({ne})</h2>"
        f"{watch_table}"
        "<p style='color:#64748b;font-size:12px;margin-top:16px'>"
        "Details und Charts im angehängten HTML-Report. Frühwarnungen melden nur Nähe zur Linie "
        "(früher, aber unsicherer als bestätigte Alerts). "
        "Heuristische Analyse historischer Kursdaten, keine Anlageberatung.</p>"
        "</div>"
    )
    msg.add_alternative(html, subtype="html")

    # ---- Anhang: voller HTML-Report mit Charts ----
    if attach_path and os.path.exists(attach_path):
        try:
            with open(attach_path, "rb") as f:
                msg.add_attachment(
                    f.read(), maintype="text", subtype="html",
                    filename=os.path.basename(attach_path),
                )
        except Exception:
            pass
    return msg


def send_email(
    signals: list[Signal], early: list[EarlyWarning], html_path: str | None, cfg
) -> bool:
    """Versendet die Alert-/Fruehwarn-Mail. Rueckgabe True bei Versand, sonst False."""
    ec = load_email_config(cfg)
    if ec is None:
        print("  E-Mail: keine/unvollstaendige Konfiguration (email_config.json) – uebersprungen.")
        return False
    if not signals and not early and not cfg.EMAIL_SEND_WHEN_EMPTY:
        print("  E-Mail: keine Treffer – kein Versand (EMAIL_SEND_WHEN_EMPTY=False).")
        return False

    msg = _build_message(signals, early, ec, html_path)
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(ec["smtp_host"], int(ec["smtp_port"]), timeout=30) as s:
            s.starttls(context=ctx)
            s.login(ec["sender_email"], ec["app_password"])
            s.send_message(msg)
        print(f"  E-Mail an {ec['recipient_email']} gesendet "
              f"({len(signals)} Alert(s), {len(early)} Fruehwarnung(en)).")
        return True
    except Exception as exc:
        print(f"  ! E-Mail-Versand fehlgeschlagen: {exc}")
        return False
