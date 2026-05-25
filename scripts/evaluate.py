"""
evaluate.py

Bewertet die aktuellen Marktdaten gegen ihre eigene Historie und berechnet:
- Sub-Score pro KPI (-2 bis +2; negativ = guenstig fuer Fixierung, positiv = unguenstig)
- Composite-Score (gewichteter Mittelwert)
- Ampel-Empfehlung (gruen / gelb-gruen / gelb / rot)
- Template-basierte Erklaertexte

Speichert das Ergebnis in data/current_assessment.json.
"""

from __future__ import annotations

import json
from datetime import datetime, date, timezone
from pathlib import Path
from statistics import mean
from typing import Literal


DATA_DIR = Path(__file__).parent.parent / "data"
HISTORY_FILE = DATA_DIR / "history.json"
ASSESSMENT_FILE = DATA_DIR / "current_assessment.json"


WEIGHTS = {
    "ch_spot": 0.40,
    "ch_hydro": 0.20,
    "fr_nuclear": 0.20,
    "de_spot": 0.20,
}


def percentile(value: float, series: list[float]) -> float:
    if not series:
        return 50.0
    below = sum(1 for v in series if v < value)
    return (below / len(series)) * 100


def trend(series: list[float], lookback: int = 4) -> Literal["steigend", "fallend", "seitwärts"]:
    if len(series) < lookback + 1:
        return "seitwärts"
    recent = series[-1]
    past = mean(series[-(lookback + 1):-1])
    if past == 0:
        return "seitwärts"
    change_pct = ((recent - past) / past) * 100
    if change_pct > 3:
        return "steigend"
    if change_pct < -3:
        return "fallend"
    return "seitwärts"


def score_spot(percentile_val: float, trend_dir: str) -> float:
    """Spotpreis: tief = guenstig (negativ)."""
    base = (percentile_val - 50) / 25
    trend_adj = {"fallend": -0.3, "seitwärts": 0.0, "steigend": +0.3}[trend_dir]
    return max(-2, min(2, base + trend_adj))


def score_hydro(percentile_val: float, trend_dir: str) -> float:
    """Hydro-Erzeugung: hoch = entspannt (guenstig, negativ); tief = Druck (ungeunstig, positiv)."""
    base = (50 - percentile_val) / 25
    trend_adj = {"fallend": +0.3, "seitwärts": 0.0, "steigend": -0.3}[trend_dir]
    return max(-2, min(2, base + trend_adj))


def score_nuclear(percentile_val: float, trend_dir: str) -> float:
    """FR Nuklear: hoch = guenstig (negativ); tief = Druck (positiv)."""
    base = (50 - percentile_val) / 25
    trend_adj = {"fallend": +0.3, "seitwärts": 0.0, "steigend": -0.3}[trend_dir]
    return max(-2, min(2, base + trend_adj))


def score_de_spot(percentile_val: float, trend_dir: str) -> float:
    """DE Spot: tief = guenstig (negativ), wirkt aehnlich wie CH Spot."""
    base = (percentile_val - 50) / 25
    trend_adj = {"fallend": -0.3, "seitwärts": 0.0, "steigend": +0.3}[trend_dir]
    return max(-2, min(2, base + trend_adj))


SCORE_FUNCTIONS = {
    "ch_spot": score_spot,
    "ch_hydro": score_hydro,
    "fr_nuclear": score_nuclear,
    "de_spot": score_de_spot,
}


def evaluate_kpi(name: str, history: list[dict]) -> dict:
    if len(history) < 2:
        return {
            "current": None,
            "percentile": None,
            "trend": "unbekannt",
            "score": 0.0,
            "data_quality": "insufficient",
        }

    values = [p["value"] for p in history]
    current = values[-1]
    p = percentile(current, values)
    t = trend(values)
    s = SCORE_FUNCTIONS[name](p, t)

    last_date = date.fromisoformat(history[-1]["date"])
    days_old = (date.today() - last_date).days
    quality = "fresh" if days_old < 14 else "stale"

    return {
        "current": current,
        "percentile": p,
        "trend": t,
        "score": s,
        "data_quality": quality,
        "last_update": history[-1]["date"],
        "history_length": len(history),
    }


def determine_recommendation(composite: float) -> dict:
    if composite < -1.0:
        return {
            "ampel": "gruen",
            "label": "Fixierung jetzt ernsthaft prüfen",
            "color_hex": "#1D9E75",
            "icon": "ti-circle-check",
        }
    if composite < -0.3:
        return {
            "ampel": "gelb-gruen",
            "label": "Attraktives Niveau – EKT-Kontakt vorbereiten",
            "color_hex": "#97C459",
            "icon": "ti-bell",
        }
    if composite < 0.5:
        return {
            "ampel": "gelb",
            "label": "Beobachten – noch nicht fixieren",
            "color_hex": "#EF9F27",
            "icon": "ti-alert-triangle",
        }
    return {
        "ampel": "rot",
        "label": "Nicht fixieren – ungünstige Marktphase",
        "color_hex": "#E24B4A",
        "icon": "ti-x",
    }


def hero_text(kpis: dict, composite: float, recommendation: dict) -> str:
    spot = kpis.get("ch_spot", {})
    hydro = kpis.get("ch_hydro", {})
    nuclear = kpis.get("fr_nuclear", {})
    de_spot = kpis.get("de_spot", {})

    parts = []

    if spot.get("current") is not None:
        p = spot["percentile"]
        if p < 25:
            parts.append(
                f"Der Schweizer Strompreis im Grosshandel liegt aktuell bei "
                f"{spot['current']:.0f} €/MWh – im historisch tiefen Bereich. "
                f"Tiefer war er in den letzten Monaten nur selten."
            )
        elif p < 50:
            parts.append(
                f"Der Schweizer Strompreis im Grosshandel liegt bei "
                f"{spot['current']:.0f} €/MWh – im unteren Mittelfeld der "
                f"letzten Monate."
            )
        elif p < 75:
            parts.append(
                f"Der Schweizer Strompreis im Grosshandel liegt bei "
                f"{spot['current']:.0f} €/MWh – im oberen Mittelfeld der "
                f"letzten Monate."
            )
        else:
            parts.append(
                f"Der Schweizer Strompreis im Grosshandel ist mit "
                f"{spot['current']:.0f} €/MWh historisch hoch."
            )

    bullish_drivers = []
    bearish_drivers = []

    if hydro.get("score", 0) > 0.5:
        bullish_drivers.append("die Schweizer Wasserkraft läuft unterdurchschnittlich")
    elif hydro.get("score", 0) < -0.5:
        bearish_drivers.append("die Schweizer Wasserkraft produziert gut")

    if nuclear.get("score", 0) > 0.5:
        bullish_drivers.append("Frankreichs Atomkraftwerke laufen schwach")
    elif nuclear.get("score", 0) < -0.5:
        bearish_drivers.append("Frankreichs Atomkraftwerke laufen gut")

    if de_spot.get("score", 0) > 0.5:
        bullish_drivers.append("der deutsche Markt ist angespannt")
    elif de_spot.get("score", 0) < -0.5:
        bearish_drivers.append("der deutsche Markt ist entspannt")

    if bullish_drivers and not bearish_drivers:
        parts.append("Die Treiber zeigen aufwärts: " + ", ".join(bullish_drivers) + ".")
    elif bearish_drivers and not bullish_drivers:
        parts.append("Die Treiber zeigen abwärts: " + ", ".join(bearish_drivers) + ".")
    elif bullish_drivers and bearish_drivers:
        parts.append(
            "Die Treiber sind gemischt – "
            + ", ".join(bullish_drivers)
            + ", aber "
            + ", ".join(bearish_drivers)
            + "."
        )
    else:
        parts.append("Die Treiber zeigen kein klares Bild – Markt ist stabil.")

    synthesis = {
        "gruen": (
            "Insgesamt ist die aktuelle Marktphase günstig für eine "
            "Preisfixierung. Wir sollten diese Woche konkret mit EKT über "
            "einen Cal-28-Fix sprechen."
        ),
        "gelb-gruen": (
            "Insgesamt ist das Niveau attraktiv, aber die Marktphase noch "
            "nicht eindeutig. Es lohnt sich, mit EKT eine unverbindliche "
            "Cal-28-Indikation einzuholen und intern die Entscheidung "
            "vorzubereiten."
        ),
        "gelb": (
            "Insgesamt überwiegt aktuell die Unsicherheit. Wir haben Zeit – "
            "weiter beobachten, keine Aktion erforderlich."
        ),
        "rot": (
            "Die aktuelle Marktphase ist ungünstig für eine Fixierung. "
            "Abwarten ist angezeigt."
        ),
    }
    parts.append(synthesis[recommendation["ampel"]])

    return " ".join(parts)


def action_text(recommendation: dict, kpis: dict) -> list[str]:
    actions = {
        "gruen": [
            "Diese Woche: EKT kontaktieren und konkrete Cal-28-Indikation einholen",
            "Geschäftsleitung über aktuelle Marktphase informieren",
            "Interner Freigabe-Prozess für Fixierung vorbereiten",
        ],
        "gelb-gruen": [
            "EKT um unverbindliche Cal-28-Indikation bitten",
            "Empfehlung intern abstimmen",
            "Nächste 2-4 Wochen verstärkt beobachten",
        ],
        "gelb": [
            "Keine Aktion erforderlich",
            "Weiter beobachten – nächster Bericht in 7 Tagen",
            "Auslöser für nächste Eskalation: signifikante Marktbewegung in einem KPI",
        ],
        "rot": [
            "Keine Fixierung",
            "Weiter beobachten – Marktphase aussitzen",
            "Bei extremer Lage (alle KPIs rot): GL informieren über Hedge-Engpass",
        ],
    }
    return actions[recommendation["ampel"]]


def main() -> int:
    with open(HISTORY_FILE, encoding="utf-8") as f:
        history = json.load(f)

    kpis = {}
    for name in ["ch_spot", "ch_hydro", "fr_nuclear", "de_spot"]:
        kpis[name] = evaluate_kpi(name, history.get(name, []))

    valid_scores = {
        name: data["score"]
        for name, data in kpis.items()
        if data["current"] is not None
    }
    if valid_scores:
        composite = sum(
            score * WEIGHTS[name] for name, score in valid_scores.items()
        ) / sum(WEIGHTS[name] for name in valid_scores)
    else:
        composite = 0.0

    recommendation = determine_recommendation(composite)
    hero = hero_text(kpis, composite, recommendation)
    actions = action_text(recommendation, kpis)

    assessment = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "week": datetime.now(timezone.utc).strftime("KW %V / %Y"),
        "composite_score": round(composite, 2),
        "recommendation": recommendation,
        "hero_text": hero,
        "actions": actions,
        "kpis": kpis,
    }

    with open(ASSESSMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(assessment, f, indent=2, ensure_ascii=False)

    print(f"Composite-Score: {composite:+.2f} → {recommendation['label']}")
    print(f"Bewertung gespeichert in {ASSESSMENT_FILE}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
