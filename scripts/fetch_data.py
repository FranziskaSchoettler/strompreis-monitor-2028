"""
fetch_data.py

Holt aktuelle Marktdaten von oeffentlichen, tokenfreien Quellen.

Quelle: energy-charts.info (Fraunhofer Institute for Solar Energy Systems ISE)
        - kein Token, keine Registrierung
        - Daten ab 2011
        - sehr stabil, akademisch betrieben

Bei jedem Lauf:
  1. Pruefe, ob Historie bereits ausreichend lang ist (>= 100 Punkte pro KPI)
  2. Wenn nein, ziehe automatisch die letzten 2 Jahre nach
  3. Sonst: nur die neuen Punkte seit dem letzten Lauf

Aktualisiert data/history.json.
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

API_BASE = "https://api.energy-charts.info"
MIN_HISTORY_POINTS = 100
BACKFILL_DAYS = 730


def load_history() -> dict:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {
        "ch_spot": [],
        "ch_reservoir": [],
        "fr_nuclear": [],
        "ttf_gas": [],
    }


def save_history(history: dict) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def merge_points(existing: list, new_points: list) -> list:
    by_date = {p["date"]: p["value"] for p in existing}
    for p in new_points:
        by_date[p["date"]] = p["value"]
    merged = [{"date": d, "value": round(v, 2)} for d, v in by_date.items()]
    merged.sort(key=lambda p: p["date"])
    return merged


def http_get(path: str, params: dict, timeout: int = 30) -> dict | None:
    url = f"{API_BASE}{path}"
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


def fetch_ch_spot(start: str, end: str) -> list[dict]:
    data = http_get("/price", {"bzn": "CH", "start": start, "end": end})
    if not data or "unix_seconds" not in data or "price" not in data:
        return []
    return aggregate_to_weekly(data["unix_seconds"], data["price"])


def fetch_fr_nuclear(start: str, end: str) -> list[dict]:
    data = http_get(
        "/public_power",
        {"country": "fr", "start": start, "end": end},
    )
    if not data or "production_types" not in data:
        return []

    nuclear_series = None
    for pt in data["production_types"]:
        if "nuclear" in pt.get("name", "").lower():
            nuclear_series = pt.get("data", [])
            break

    if not nuclear_series or "unix_seconds" not in data:
        return []

    timestamps = data["unix_seconds"]
    installed_mw = 61_400
    availability = [
        (v / installed_mw) * 100 if v is not None else None
        for v in nuclear_series
    ]
    return aggregate_to_weekly(timestamps, availability)


def fetch_ch_reservoir(start: str, end: str) -> list[dict]:
    data = http_get(
        "/reservoir_filling_level",
        {"country": "ch", "start": start[:10], "end": end[:10]},
    )
    if data and "data" in data and "unix_seconds" in data:
        values = data["data"]
        max_v = max((v for v in values if v is not None), default=100)
        if max_v > 100:
            values = [
                (v / 8_800_000) * 100 if v is not None else None
                for v in values
            ]
        return aggregate_to_weekly(data["unix_seconds"], values)

    return []


def fetch_ttf_gas(start: str, end: str) -> list[dict]:
    data = http_get("/price", {"bzn": "TTF_DA", "start": start, "end": end})
    if data and "unix_seconds" in data and "price" in data:
        return aggregate_to_weekly(data["unix_seconds"], data["price"])
    return []


def needs_backfill(history: dict) -> bool:
    return any(
        len(history.get(name, [])) < MIN_HISTORY_POINTS
        for name in ["ch_spot", "ch_reservoir", "fr_nuclear", "ttf_gas"]
    )


def fetch_window(start_iso: str, end_iso: str) -> dict[str, list[dict]]:
    print(f"  Fenster: {start_iso} bis {end_iso}")
    return {
        "ch_spot": fetch_ch_spot(start_iso, end_iso),
        "ch_reservoir": fetch_ch_reservoir(start_iso, end_iso),
        "fr_nuclear": fetch_fr_nuclear(start_iso, end_iso),
        "ttf_gas": fetch_ttf_gas(start_iso, end_iso),
    }


def main() -> int:
    history = load_history()

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
    print(f"\nFertig. Insgesamt {sum(len(v) for v in history.values())} Datenpunkte in der Historie.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
