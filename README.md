# Schaffner Strompreis-Monitor 2028

Wöchentlicher, vollautomatischer Beobachtungs-Agent für die Entscheidung
"Wann fixieren wir den Strompreis für das Lieferjahr 2028 bei EKT?"

## Was macht dieser Agent

Jeden Montag morgen sammelt ein automatischer Job mehrere öffentliche
Marktdaten, bewertet sie nach einem festen Modell und generiert einen
Wochenbericht in Form eines Dashboards.

Das Dashboard zeigt dir auf einen Blick:
- ob diese Woche ein günstiges Zeitfenster für die Fixierung ist
- welche Marktindikatoren in welche Richtung zeigen
- konkrete Handlungsempfehlung in Klartext

## Wie das Modell funktioniert

Da der EEX Swiss Cal-28 Future nicht gratis automatisch abrufbar ist,
beobachten wir stattdessen vier Indikatoren, die nachweislich die
Schweizer Forward-Preise treiben:

1. **Schweizer Spotpreis** (Swissix Day-Ahead)
2. **Schweizer Speicherseen-Füllstand**
3. **Französische Atomkraft-Verfügbarkeit**
4. **Europäischer Gaspreis TTF**

Alle Daten kommen von **energy-charts.info** (Fraunhofer Institute for
Solar Energy Systems ISE). Diese Quelle ist gratis, ohne Anmeldung
nutzbar, und stellt Daten ab 2011 bereit. Beim ersten Lauf des Agents
werden automatisch die letzten 2 Jahre Historie geladen.

Jeder Indikator wird gegen seine eigene Historie verglichen (Perzentil,
Trend, saisonaler Vergleich) und in einen Sub-Score umgerechnet. Die
Sub-Scores werden gewichtet zu einem Composite-Score zusammengefasst,
der die Ampel im Dashboard steuert.

## Wichtige Einschränkung

Der Agent zeigt dir **nicht den exakten Cal-28 Forward-Preis**, sondern
die **Marktstimmung** dafür. Wenn das Modell auf Grün geht, fragst du
EKT nach einer konkreten Cal-28-Indikation und triffst die finale
Entscheidung.

Die Empfehlungen ersetzen keine Beratung durch Energiehändler oder
Treasury-Experten. Sie sind ein Entscheidungs-Hilfsmittel, nicht der
Entscheid selbst.

## Architektur

```
.github/workflows/weekly.yml   → läuft jeden Montag 06:00 UTC
scripts/fetch_data.py          → holt aktuelle Marktdaten
scripts/evaluate.py            → bewertet, baut Composite-Score
scripts/build_dashboard.py     → generiert docs/index.html
data/                          → historische Snapshots (versioniert in Git)
docs/index.html                → das Dashboard (GitHub Pages)
```

## Setup

Siehe `SETUP.md` für Schritt-für-Schritt-Anleitung.

## Kosten

Null Franken laufend. Keine Anmeldung, kein Token, keine Kreditkarte.
Alle Datenquellen sind gratis und tokenfrei. GitHub Actions und
GitHub Pages sind für öffentliche Repos unbegrenzt kostenlos.

## Lizenz

Internes Werkzeug Schaffner. Nicht zur Weitergabe bestimmt.
