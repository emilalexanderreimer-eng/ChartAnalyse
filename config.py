"""
Zentrale Konfiguration der Chartanalyse.

Alle Stellschrauben der Analyse stehen hier an einem Ort und sind kommentiert,
damit du das Verhalten anpassen kannst, ohne den restlichen Code zu verstehen.
Strengere Werte  -> weniger, aber sicherere Alerts.
Lockerere Werte  -> mehr Alerts, aber mehr Fehlsignale.
"""

# ----------------------------------------------------------------------------
# Daten
# ----------------------------------------------------------------------------
# Wie viel Historie wird geladen (Yahoo-Notation: "6mo", "1y", "2y", "5y").
HISTORY_PERIOD = "1y"
# Zeit-Intervall der Kerzen. "1d" = Tageskerzen (Standard fuer diese Analyse).
INTERVAL = "1d"
# In wie vielen Tickern pro Download-Anfrage gebuendelt wird (schont das API).
DOWNLOAD_CHUNK_SIZE = 50

# ----------------------------------------------------------------------------
# Support / Resistance Erkennung
# ----------------------------------------------------------------------------
# Ein Swing-Hoch/Tief gilt als Pivot, wenn es das Hoch/Tief in diesem Fenster
# links UND rechts ist. Groesser = nur markantere Wendepunkte.
PIVOT_LEFT = 5
PIVOT_RIGHT = 5
# Zwei Pivots gelten als dieselbe Linie/Zone, wenn ihr Abstand <= dieser
# Prozentsatz ist (0.012 = 1,2 %). Groesser = breitere Zonen, weniger Linien.
LEVEL_TOLERANCE = 0.012
# Eine Linie muss mindestens so oft beruehrt worden sein, um als "validiert"
# zu zaehlen. 1 = jede Spitze zaehlt (schwach), 2+ = nur bestaetigte Zonen.
MIN_TOUCHES = 2

# ----------------------------------------------------------------------------
# Reversal-/Umkehr-Erkennung (das Herzstueck der Alerts)
# ----------------------------------------------------------------------------
# Wie nah die aktuelle Kerze an die Linie heran muss, um als "Beruehrung" zu
# zaehlen (Anteil des Linienpreises). 0.005 = 0,5 %.
TOUCH_ZONE = 0.006
# Wie weit die Kerze die Linie kurz durchstechen darf (Anteil). Ein Durchstich
# mit Rueckkehr ist ein staerkeres Umkehrsignal als ein blosses Antippen.
PIERCE_TOLERANCE = 0.010
# Mindestanteil des Dochtes (Rejection-Wick) an der gesamten Kerzenspanne.
# 0.45 = der ablehnende Docht muss >= 45 % der Kerze ausmachen.
MIN_WICK_RATIO = 0.45
# Volumen der Umkehrkerze relativ zum 20-Tage-Schnitt. 1.0 = mind. Durchschnitt.
MIN_VOLUME_RATIO = 1.0
# Optional: verlangt, dass die VOR-Kerze die Zone bereits angetestet hat
# (Zwei-Kerzen-Bestaetigung). Strenger, aber sicherer.
REQUIRE_PRIOR_TOUCH = False

# ----------------------------------------------------------------------------
# Confidence / Alert-Schwelle
# ----------------------------------------------------------------------------
# Nur Signale mit Confidence >= diesem Wert (0-100) werden als Alert gemeldet.
# Hoeher = weniger, aber ueberzeugtere Alerts.
CONFIDENCE_THRESHOLD = 65

# Gewichtung der Confidence-Bausteine (Summe sollte ~1.0 sein):
W_LEVEL_STRENGTH = 0.40   # wie stark/oft bestaetigt die Linie ist
W_CANDLE_QUALITY = 0.40   # wie ausgepraegt die Umkehrkerze ist
W_VOLUME = 0.20           # Volumenbestaetigung

# ----------------------------------------------------------------------------
# Fruehwarner (zweite, FRUEHERE Kategorie)
# ----------------------------------------------------------------------------
# Meldet, wenn der aktuelle Kurs JETZT direkt an einer starken Linie sitzt –
# noch OHNE bestaetigte Umkehrkerze. Das warnt frueher als der Reversal-Alert
# ("Achtung, X testet gerade die Linie"), ist aber unsicherer.
EARLY_WARNING_ENABLED = True
# "Direkt an der Linie" = Schlusskurs innerhalb dieses Abstands (0.005 = 0,5 %).
EARLY_WARNING_ZONE = 0.005
# Nur SEHR starke Linien fruehwarnen (0..1; haelt die Liste kurz & relevant).
EARLY_WARNING_MIN_STRENGTH = 0.65
# Nur warnen, wenn der Kurs HEUTE frisch an die Linie kam (gestern noch
# ausserhalb der Zone). Verhindert taegliche Dauerwarnungen fuer dasselbe
# Setup und trifft genau "der Kurs trifft GERADE die Linie". False = jeden
# Tag warnen, solange der Kurs in der Zone bleibt.
EARLY_WARNING_ONLY_FRESH = True

# ----------------------------------------------------------------------------
# Ausgabe
# ----------------------------------------------------------------------------
OUTPUT_DIR = "output"
GENERATE_CHARTS = True       # PNG-Chart je Alert (im HTML eingebettet)
CHART_LOOKBACK_BARS = 120    # wie viele Kerzen der Chart zeigt
OPEN_HTML_WHEN_DONE = True   # Report nach Lauf automatisch im Browser oeffnen

# ----------------------------------------------------------------------------
# E-Mail-Benachrichtigung (optional)
# ----------------------------------------------------------------------------
# Aktiv nur, wenn main.py mit --email gestartet wird (so macht es die geplante
# Aufgabe). Die Zugangsdaten (inkl. App-Passwort) stehen NICHT hier, sondern in
# einer separaten, nicht versionierten Datei email_config.json (siehe
# email_config.example.json). Fehlt/ungueltig -> E-Mail wird einfach uebersprungen.
EMAIL_CONFIG_FILE = "email_config.json"
EMAIL_SEND_WHEN_EMPTY = False  # True = auch mailen, wenn es 0 Alerts gibt

# ----------------------------------------------------------------------------
# DEMA + SuperTrend Strategie-Filter (fuer Fruehwarnungen)
# ----------------------------------------------------------------------------
# Fruehwarnungen erscheinen NUR, wenn DEMA und SuperTrend in dieselbe Richtung
# zeigen UND eine S/R-Linie gerade angefahren wird, die in dieser Richtung
# durchbrochen werden koennte:
#   Bullish (Kurs > DEMA, ST gruen)  -> warnt bei RESISTANCE-Linien (Ausbruch hoch)
#   Bearish (Kurs < DEMA, ST rot)    -> warnt bei SUPPORT-Linien    (Ausbruch tief)
# Zeigen DEMA und ST in verschiedene Richtungen: KEINE Fruehwarnung.
DEMA_PERIOD = 200        # Laenge des Double EMA (aus TradingLab-Video)
ST_ATR_PERIOD = 12       # ATR-Periode des SuperTrend
ST_MULTIPLIER = 3.0      # ATR-Multiplikator des SuperTrend
