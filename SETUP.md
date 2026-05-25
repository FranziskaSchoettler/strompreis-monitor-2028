# Setup-Anleitung

Schritt fuer Schritt vom leeren GitHub-Account zum laufenden Dashboard.
Zeitaufwand: ca. 10 Minuten. Kein Token noetig, keine Kosten.

## Voraussetzungen

- GitHub-Account (gratis reicht)

Mehr nicht. Keine Anmeldung bei Datenquellen, keine API-Keys, keine
Kreditkarte.

## Schritt 1: Repo auf GitHub anlegen

1. Auf https://github.com/new gehen
2. Repository-Name z.B. `schaffner-strom-2028`
3. **Public** waehlen (siehe Hinweis unten)
4. "Create repository" klicken

**Warum public?** Damit GitHub Pages und GitHub Actions kostenlos
unbegrenzt laufen. Im Repo sind nur oeffentliche Marktdaten und Code
keine Geschaeftsgeheimnisse von Schaffner. Wenn das nicht passt:
private Repo geht auch, dann brauchst du GitHub Pro fuer privates
GitHub Pages.

## Schritt 2: Code hochladen

Drei Varianten, je nach deinem Komfort mit Git:

**Variante A (einfachste, ueber die Webseite):**
1. ZIP entpacken
2. Auf der frischen Repo-Seite den Link "uploading an existing file"
3. Alle Dateien und Ordner aus dem entpackten Ordner hochladen
4. "Commit changes" klicken

**Variante B (per Git):**
```bash
git clone https://github.com/<dein-username>/schaffner-strom-2028.git
cd schaffner-strom-2028
# Dateien aus dem ZIP hereinkopieren
git add .
git commit -m "Initial commit"
git push
```

## Schritt 3: GitHub Pages aktivieren

Im Repo auf GitHub:

1. `Settings` -> `Pages`
2. Source: `Deploy from a branch`
3. Branch: `main` / Folder: `/docs`
4. Speichern

Nach 1-2 Minuten ist das Dashboard erreichbar unter:
`https://<dein-username>.github.io/schaffner-strom-2028/`

## Schritt 4: Ersten Lauf manuell ausloesen

1. Im Repo auf GitHub: `Actions`
2. Falls Actions deaktiviert sind, "I understand my workflows" klicken
3. `Weekly Report` auswaehlen
4. `Run workflow` -> `Run workflow` klicken
5. Warten (3-5 Minuten - der erste Lauf macht den 2-Jahres-Backfill)
6. Wenn der gruene Haken erscheint, ist das Dashboard live

## Schritt 5: Pruefen

Oeffne `https://<dein-username>.github.io/schaffner-strom-2028/`.

Du solltest sehen:
- Hero-Karte oben mit Empfehlung
- 4 KPI-Karten mit jeweils 2 Jahren Verlauf
- "Was diese Woche zu tun ist" unten

## Automatik

Ab jetzt laeuft der Workflow jeden Montag morgen automatisch.
Du musst nichts tun. Wenn du am Dienstag morgen Zeit hast, schaust du
ins Dashboard.

## Wenn etwas nicht funktioniert

- **Workflow scheitert:** Klicke auf den gescheiterten Lauf unter
  `Actions`, schau in die Logs. Meistens ist es ein API-Endpunkt von
  energy-charts.info, der sich geaendert hat. Sag mir Bescheid, ich
  helfe beim Anpassen.
- **Dashboard ist leer:** Eventuell hat eine Datenquelle gerade
  ausgesetzt. Beim naechsten Lauf wieder probieren. Die Verlaufsdaten
  bleiben sicher in `data/history.json` versioniert.
- **Dashboard zeigt veraltete Werte:** GitHub Pages braucht 2-5 Minuten
  nach einem Commit. Browser-Cache loeschen hilft manchmal.

## Wartung

- **Quartalsweise:** Schau ob die Workflows gruen durchlaufen
- **Bei API-Aenderungen:** energy-charts.info ist sehr stabil, aber
  nicht garantiert. Falls die Endpunkte sich aendern, muss
  `scripts/fetch_data.py` angepasst werden
- **Wenn EKT-Kontakt naeher rueckt:** Bis dahin hast du eine grosse
  Datenbasis gesammelt - du kannst dann informiert ins Gespraech gehen
