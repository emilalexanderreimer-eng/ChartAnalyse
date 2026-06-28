# Chartanalyse – S&P 500 Support/Resistance Reversal-Scanner

Scannt täglich die ~500 Aktien des S&P 500 und meldet **nur fundierte
Umkehr-Signale**: also genau dann, wenn der Kurs eine **starke**
Support- oder Resistance-Linie berührt **und** dort mit einer **bestätigten
Umkehr-Kerze** tatsächlich dreht.

## Schnellstart (Windows)

1. **`run.bat` doppelklicken.**
   Beim ersten Mal richtet sich die App selbst ein (virtuelle Umgebung +
   Pakete, dauert ein paar Minuten). Danach startet jeder Lauf in Sekunden.
2. Am Ende öffnet sich automatisch ein **HTML-Report** im Browser mit den
   Alerts und einem Chart je Signal (Linie + Umkehrkerze markiert).

Ergebnisse landen außerdem im Ordner `output/` als CSV.

## Manueller Start (Konsole)

```powershell
python main.py                  # kompletter S&P-500-Scan
python main.py --limit 30       # schneller Test mit 30 Aktien
python main.py --tickers AAPL,MSFT,NVDA
python main.py --threshold 75   # nur sehr sichere Signale
python main.py --no-charts      # schneller, ohne Chartbilder
python main.py --refresh-universe  # S&P-500-Liste neu von Wikipedia laden
```

> Tipp: Am besten **nach US-Börsenschluss** (nach ca. 22:00 MEZ) laufen
> lassen, damit die letzte Tageskerze abgeschlossen ist.

## Wie die Alerts entstehen

1. **Linien-Erkennung** – Aus 1 Jahr Tageskursen werden Swing-Hochs/-Tiefs
   gesucht und zu Zonen geclustert. Jede Zone bekommt eine **Stärke** aus
   *Anzahl Berührungen* + *Aktualität*.
2. **Umkehr-Prüfung** der letzten Kerze gegen jede Linie. Ein Signal verlangt:
   - Tief/Hoch **berührt oder durchsticht** die Linie,
   - **Ablehnungs-Docht** (langer Wick) ≥ 45 % der Kerze,
   - **Schluss zurück** auf der richtigen Seite der Linie,
   - **Volumen** mindestens im Tagesdurchschnitt.
3. **Confidence-Score (0–100)** aus Linien-Stärke + Kerzen-Qualität + Volumen.
   Nur Werte **≥ 65** (Standard) werden gemeldet.

Dass an manchen Tagen **null Alerts** kommen, ist normal und gewollt – echte,
bestätigte Umkehrungen sind selten.

## Zwei Kategorien: Alert vs. Frühwarner

Der Report (und die E-Mail) hat **zwei getrennte Abschnitte**:

1. **✅ Bestätigte Reversal-Alerts** – wie oben: starke Linie **+ bestätigte
   Umkehrkerze + Volumen**, Confidence ≥ 65. Die wenigen, hochsicheren Signale.
2. **⚠️ Frühwarnungen** – meldet, wenn der Kurs **heute frisch** an eine **sehr
   starke** Linie gelaufen ist (innerhalb 0,5 %), **noch ohne** bestätigte
   Umkehr. Das warnt *früher* („X testet gerade die Linie"), ist aber
   unsicherer – eine Beobachtungsliste, kein fertiges Signal.

„Frisch" heißt: gestern war der Kurs noch außerhalb der Zone – so gibt es keine
täglichen Dauerwarnungen für dasselbe Setup. Regler dafür in `config.py`:
`EARLY_WARNING_ZONE`, `EARLY_WARNING_MIN_STRENGTH`, `EARLY_WARNING_ONLY_FRESH`
(oder `EARLY_WARNING_ENABLED = False` zum Abschalten).

## Einstellungen

Alle Stellschrauben stehen kommentiert in [`config.py`](config.py).
Wichtigste Werte:

| Einstellung | Bedeutung |
|---|---|
| `CONFIDENCE_THRESHOLD` | Alert-Schwelle (höher = weniger, sicherer) |
| `MIN_TOUCHES` | wie oft eine Linie bestätigt sein muss |
| `MIN_WICK_RATIO` | wie ausgeprägt der Umkehr-Docht sein muss |
| `MIN_VOLUME_RATIO` | Volumen-Mindestbestätigung |
| `REQUIRE_PRIOR_TOUCH` | Zwei-Kerzen-Bestätigung (strenger) |
| `HISTORY_PERIOD` | wie viel Historie geladen wird |
| `EARLY_WARNING_ZONE` | wie nah „an der Linie" für den Frühwarner (0,5 %) |
| `EARLY_WARNING_MIN_STRENGTH` | Mindeststärke der Linie für Frühwarnung |
| `EARLY_WARNING_ONLY_FRESH` | nur bei frischem Eintritt in die Zone warnen |

## Reports im Browser durchsuchen (Viewer)

Statt einzelne HTML-Dateien zu öffnen, kannst du alle bisherigen Reports über
einen kleinen lokalen Webserver durchblättern (nur Python-Standardbibliothek,
kein extra Paket):

```powershell
python viewer.py            # öffnet http://localhost:8000
python viewer.py --port 8080
```

Die Startseite listet alle Reports (neueste zuerst) mit CSV-Download; ein Klick
öffnet den jeweiligen Report inkl. Charts. Beenden mit `Strg+C`. Der Viewer ist
auch in [`.claude/launch.json`](.claude/launch.json) als Konfiguration
„Report Viewer" hinterlegt.

## E-Mail-Benachrichtigung einrichten

Bei Alerts kann die App dir eine E-Mail schicken (mit Übersichtstabelle + dem
HTML-Report als Anhang). Einmalig einrichten:

1. **Gmail-App-Passwort erstellen** (das normale Passwort funktioniert nicht):
   - 2-Faktor-Authentifizierung muss aktiv sein.
   - Unter <https://myaccount.google.com/apppasswords> ein App-Passwort anlegen
     (16 Zeichen).
2. Datei **`email_config.example.json` kopieren** zu **`email_config.json`**
   und das App-Passwort eintragen (Absender/Empfänger sind schon auf deine
   Adresse gesetzt). Diese Datei bleibt lokal (steht in `.gitignore`).

Test: `python main.py --tickers AAPL,MSFT --email`
(schickt nur eine Mail, wenn es tatsächlich einen Alert gibt; Verhalten über
`EMAIL_SEND_WHEN_EMPTY` in `config.py` änderbar).

## Täglicher Automatik-Lauf (eingerichtet)

Eine Windows-Aufgabe **„Chartanalyse Daily"** ist bereits angelegt: Sie führt
`scheduled_run.bat` **werktags um 22:30** aus (kompletter S&P-500-Scan, kein
Fenster, schreibt `output/scan.log`, sendet bei Alerts E-Mail).

- Voraussetzung: Der PC ist um 22:30 an und du bist angemeldet. War der PC aus,
  wird der Lauf nachgeholt, sobald er wieder läuft (*StartWhenAvailable*).
- **Sofort testen:** `Start-ScheduledTask -TaskName "Chartanalyse Daily"`
- **Uhrzeit/Tage ändern, deaktivieren, löschen:** in der **Aufgabenplanung**
  (`taskschd.msc`) unter „Chartanalyse Daily", oder per PowerShell:
  ```powershell
  Disable-ScheduledTask -TaskName "Chartanalyse Daily"   # pausieren
  Enable-ScheduledTask  -TaskName "Chartanalyse Daily"   # wieder aktiv
  Unregister-ScheduledTask -TaskName "Chartanalyse Daily" -Confirm:$false  # entfernen
  ```

## Hinweis

Heuristische Analyse historischer Kursdaten (Quelle: Yahoo Finance über
`yfinance`). **Keine Anlageberatung**, keine Erfolgsgarantie.
