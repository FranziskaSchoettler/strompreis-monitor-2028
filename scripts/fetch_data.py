"""
fetch_data.py

Holt aktuelle Marktdaten von oeffentlichen, tokenfreien Quellen.

Quelle: energy-charts.info (Fraunhofer Institute for Solar Energy Systems ISE)
        - kein Token, keine Registrierung
        - Daten ab 2011
        - sehr stabil, akademisch betrieben

Endpunkte:
  /price          - Spotpreise nach Marktgebiet
  /public_power   - Erzeugung nach Produktionstyp und Land

KPIs:
  1. CH Spot Day-Ahead (Swissix)
  2. CH Wasserkraft-Erzeugung (Proxy fuer Hydro-Verfuegbarkeit / Speicher)
  3. FR Nuklear-Erzeugung (Proxy fuer KKW-Verfuegbarkeit)
  4. DE Spot Day-Ahead (Proxy fuer europaeischen Marktstress, korreliert mit Gas)

EUR/CHF-Kurs:
  Wir holen den aktuellen Kurs einmal pro Lauf von der SNB (oeffentlich,
  ohne Token) und speichern ihn fuer die Anzeige.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from statistics import mean

import requests


DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"
META_FILE = DATA_DIR / "meta.json"

API_BASE = "https://api.energy-charts.info"
MIN_HISTORY_POINTS = 80
BACKFILL_DAYS = 730

# Installierte Kapazitaeten als Referenz fuer Verfuegbarkeits-Berechnung
FR_NUCLEAR_INSTALLED_MW = 61_400  # FR Atomkraft-Flotte
CH_HYDRO_INSTALLED_MW = 17_500    # CH Wasserkraft (Laufwasser + Speicher)


def load_history() -> dict:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "ch_spot": [],
        "ch_hydro": [],
        "fr_nuclear": [],
        "de_spot": [],
    }


def save_history(history: dict) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def save_meta(meta: dict) -> None:
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def merge_points(existing: list, new_points: list) -> list:
    by_date = {p["date"]: p["value"] for p in existing}
    for p in new_points:
        by_date[p["date"]] = p["value"]
    merged = [{"date": d, "value": round(v, 2)} for d, v in by_date.items()]
    merged.sort(key=lambda p: p["date"])
    return merged


def http_get(url: str, params: dict | None = None, timeout: int = 30) -> dict | None:
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            print(f"  HTTP {r.status_code} fuer {url} (Versuch {attempt + 1})", file=sys.stderr)
        except Exception as e:
            print(f"  Fehler {url}: {e} (Versuch {attempt + 1})", file=sys.stderr)
    return None


def aggregate_to_weekly(timestamps: list, values: list) -> list[dict]:
    if not timestamps or not values:
        return []

    dates = []
    for t in timestamps:
        if isinstance(t, (int, float)):
            d = datetime.fromtimestamp(t, tz=timezone.utc).date()
        else:
            d = date.fromisoformat(str(t)[:10])
        dates.append(d)

    weekly: dict[str, list[float]] = {}
    for d, v in zip(dates, values):
        if v is None:
            continue
        iso_year, iso_week, _ = d.isocalendar()
        monday = date.fromisocalendar(iso_year, iso_week, 1)
        key = monday.isoformat()
        weekly.setdefault(key, []).append(float(v))

    return [
        {"date": k, "value": round(mean(weekly[k]), 2)}
        for k in sorted(weekly.keys())
    ]


def fetch_price(bzn: str, start: str, end: str) -> list[dict]:
    """Holt Spotpreis fuer ein Marktgebiet und aggregiert zu Wochenmittel."""
    data = http_get(f"{API_BASE}/price", {"bzn": bzn, "start": start, "end": end})
    if not data or "unix_seconds" not in data or "price" not in data:
        return []
    return aggregate_to_weekly(data["unix_seconds"], data["price"])


def fetch_production_share(country: str, production_keywords: list[str],
                            installed_mw: int, start: str, end: str) -> list[dict]:
    """
    Holt Erzeugung eines bestimmten Produktionstyps fuer ein Land und
    rechnet in Prozent der installierten Kapazitaet um.

    production_keywords: Liste von Schluesselwoertern, die im 'name' des
                         Produktionstyps stehen koennen (case-insensitive).
    """
    data = http_get(
        f"{API_BASE}/public_power",
        {"country": country, "start": start, "end": end},
    )
    if not data or "production_types" not in data:
        return []

    # Finde alle passenden Produktionstypen und addiere sie auf
    matching_series = []
    for pt in data["production_types"]:
        name = pt.get("name", "").lower()
        if any(kw.lower() in name for kw in production_keywords):
            series = pt.get("data", [])
            if series:
                matching_series.append(series)

    if not matching_series:
        print(f"  Keine passenden Produktionstypen gefunden fuer {country} mit {production_keywords}", file=sys.stderr)
        return []

    timestamps = data.get("unix_seconds", [])
    if not timestamps:
        return []

    # Summiere alle passenden Serien zeitpunktweise
    n = len(timestamps)
    summed = [0.0] * n
    for series in matching_series:
        for i in range(min(n, len(series))):
            v = series[i]
            if v is not None:
                summed[i] += v

    # In Prozent der installierten Kapazitaet umrechnen
    availability = [
        (v / installed_mw) * 100 if v > 0 else None
        for v in summed
    ]
    return aggregate_to_weekly(timestamps, availability)


def fetch_ch_spot(start: str, end: str) -> list[dict]:
    return fetch_price("CH", start, end)


def fetch_de_spot(start: str, end: str) -> list[dict]:
    return fetch_price("DE-LU", start, end)


def fetch_ch_hydro(start: str, end: str) -> list[dict]:
    """CH Wasserkraft-Erzeugung (Laufwasser + Speicher) als % der installierten Kapazitaet."""
    return fetch_production_share(
        "ch",
        ["hydro", "wasser"],
        CH_HYDRO_INSTALLED_MW,
        start, end,
    )


def fetch_fr_nuclear(start: str, end: str) -> list[dict]:
    return fetch_production_share(
        "fr",
        ["nuclear", "kern"],
        FR_NUCLEAR_INSTALLED_MW,
        start, end,
    )


def fetch_eur_chf() -> float | None:
    """Holt aktuellen EUR/CHF Wechselkurs von der SNB. Tokenfrei, oeffentlich."""
    # SNB hat einen JSON-Endpunkt; alternativ frankfurter.app (ECB-Daten, ebenfalls gratis)
    try:
        r = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "EUR", "to": "CHF"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if "rates" in data and "CHF" in data["rates"]:
                return float(data["rates"]["CHF"])
    except Exception as e:
        print(f"  EUR/CHF-Kurs nicht abrufbar: {e}", file=sys.stderr)
    return None


def needs_backfill(history: dict) -> bool:
    return any(
        len(history.get(name, [])) < MIN_HISTORY_POINTS
        for name in ["ch_spot", "ch_hydro", "fr_nuclear", "de_spot"]
    )


def fetch_window(start_iso: str, end_iso: str) -> dict[str, list[dict]]:
    print(f"  Fenster: {start_iso} bis {end_iso}")
    return {
        "ch_spot": fetch_ch_spot(start_iso, end_iso),
        "ch_hydro": fetch_ch_hydro(start_iso, end_iso),
        "fr_nuclear": fetch_fr_nuclear(start_iso, end_iso),
        "de_spot": fetch_de_spot(start_iso, end_iso),
    }


def main() -> int:
    history = load_history()

    # Migration: alte Keys auf neue umschreiben, falls vorhanden
    if "ch_reservoir" in history and "ch_hydro" not in history:
        history["ch_hydro"] = []
        del history["ch_reservoir"]
    if "ttf_gas" in history and "de_spot" not in history:
        history["de_spot"] = []
        del history["ttf_gas"]
    # Sicherstellen, dass alle Keys vorhanden sind
    for key in ["ch_spot", "ch_hydro", "fr_nuclear", "de_spot"]:
        history.setdefault(key, [])

    if needs_backfill(history):
        print("Erster Lauf oder kurze Historie - starte Backfill (2 Jahre).")
        end = date.today()
        start = end - timedelta(days=BACKFILL_DAYS)

        current = start
        all_results: dict[str, list[dict]] = {k: [] for k in history.keys()}
        while current < end:
            block_end = min(current + timedelta(days=90), end)
            block_results = fetch_window(current.isoformat(), block_end.isoformat())
            for k, points in block_results.items():
                all_results[k].extend(points)
            current = block_end

        for name, points in all_results.items():
            before = len(history.get(name, []))
            history[name] = merge_points(history.get(name, []), points)
            print(f"  {name}: {before} -> {len(history[name])} Punkte")
    else:
        print("Historie ausreichend - hole nur die letzten 14 Tage.")
        end = date.today()
        start = end - timedelta(days=14)
        results = fetch_window(start.isoformat(), end.isoformat())
        for name, points in results.items():
            before = len(history.get(name, []))
            history[name] = merge_points(history.get(name, []), points)
            added = len(history[name]) - before
            print(f"  {name}: +{added} neue Punkte ({len(history[name])} gesamt)")

    save_history(history)

    # Wechselkurs holen
    rate = fetch_eur_chf()
    meta = {
        "last_update": datetime.now(timezone.utc).isoformat(),
        "eur_chf_rate": rate,
    }
    save_meta(meta)
    if rate:
        print(f"\nEUR/CHF: {rate:.4f}")

    total = sum(len(v) for v in history.values())
    print(f"\nFertig. Insgesamt {total} Datenpunkte in der Historie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
