"""
build_dashboard.py

Generiert docs/index.html aus data/current_assessment.json + data/history.json + data/meta.json.
Statisches HTML, Tailwind via CDN, Chart.js via CDN, Geist Font.
Light + Dark Mode automatisch.
Anzeige EUR primaer, CHF in Klammern.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone


DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = Path(__file__).parent.parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)


KPI_META = {
    "ch_spot": {
        "title": "Schweizer Strompreis im Grosshandel",
        "subtitle": "Was zahlen Stromhändler heute pro Megawattstunde an der Schweizer Börse",
        "unit": "€/MWh",
        "is_price": True,
        "chart_explanation": (
            "Der Schweizer Spotpreis zeigt das aktuelle Marktstimmungsbild. "
            "Tiefe Werte weisen auf entspannte Marktphasen hin, hohe Werte "
            "auf Knappheit oder Stress."
        ),
        "relevance": (
            "Der Spotpreis ist nicht der Preis, den wir für 2028 fixieren würden, "
            "aber er bewegt sich eng mit den Forward-Preisen. Wenn der Spot "
            "anhaltend tief ist, sind tendenziell auch die Forwards tief."
        ),
        "format": "{:.0f}",
    },
    "ch_hydro": {
        "title": "Schweizer Wasserkraft-Erzeugung",
        "subtitle": "Wie stark produzieren die CH-Wasserkraftwerke aktuell, in Prozent der installierten Kapazität",
        "unit": "%",
        "is_price": False,
        "chart_explanation": (
            "Die Wasserkraft-Erzeugung folgt einem klaren Jahresrhythmus: hoch im "
            "Frühling und Sommer (Schmelzwasser), tiefer im Winter. Abweichungen "
            "vom langjährigen Schnitt deuten auf Hydro-Stress oder Hydro-Überfluss."
        ),
        "relevance": (
            "Schwache Wasserkraft zwingt die Schweiz zu mehr Stromimport und treibt "
            "die Preise. Starke Wasserkraft entspannt den Markt und drückt die "
            "Forward-Preise für 2028."
        ),
        "format": "{:.1f}",
    },
    "fr_nuclear": {
        "title": "Verfügbarkeit französischer Atomkraftwerke",
        "subtitle": "Anteil der installierten Nuklearleistung, der tatsächlich Strom produziert",
        "unit": "%",
        "is_price": False,
        "chart_explanation": (
            "Frankreich ist Europas grösster Stromexporteur. Wenn Reaktoren "
            "ausfallen, fehlt billiger Atomstrom im Markt – die Preise "
            "steigen quer durch Europa, auch in der Schweiz."
        ),
        "relevance": (
            "Tiefe FR-Nuklearverfügbarkeit ist einer der wichtigsten "
            "Aufwärtstreiber für CH-Forwards. Hohe Verfügbarkeit drückt die "
            "Preise."
        ),
        "format": "{:.0f}",
    },
    "de_spot": {
        "title": "Deutscher Strompreis (Marktstress-Indikator)",
        "subtitle": "Spotpreis im grössten europäischen Strommarkt, korreliert stark mit CH",
        "unit": "€/MWh",
        "is_price": True,
        "chart_explanation": (
            "Der deutsche Strommarkt ist der grösste und liquideste in Europa. "
            "Seine Preisbewegungen treiben den gesamten Kontinent inklusive der "
            "Schweiz. Hohe DE-Preise deuten oft auf Gas-Knappheit, Kohle-Stress "
            "oder geringe Erneuerbaren-Produktion."
        ),
        "relevance": (
            "Wenn DE anhaltend teuer ist, sind auch die CH-Forwards für 2028 "
            "teuer. Wenn DE entspannt, hat das einen direkten dämpfenden "
            "Effekt auf den CH-Markt."
        ),
        "format": "{:.0f}",
    },
}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Strompreis-Monitor 2028</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  :root {{
    --bg: #FAFAFA; --surface: #FFFFFF;
    --text: #0A0A0A; --text-muted: #6B6B6B; --text-faint: #9B9B9B;
    --border: rgba(0,0,0,0.08); --border-strong: rgba(0,0,0,0.16);
    --accent: #185FA5; --success: #1D9E75; --warning: #BA7517; --danger: #A32D2D;
    --success-soft: #EAF3DE; --warning-soft: #FAEEDA; --danger-soft: #FCEBEB; --info-soft: #E6F1FB;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0A0A0A; --surface: #141414;
      --text: #FAFAFA; --text-muted: #9B9B9B; --text-faint: #6B6B6B;
      --border: rgba(255,255,255,0.08); --border-strong: rgba(255,255,255,0.16);
      --accent: #5B9BD5; --success: #5DCAA5; --warning: #EF9F27; --danger: #E24B4A;
      --success-soft: rgba(29,158,117,0.15); --warning-soft: rgba(186,117,23,0.15);
      --danger-soft: rgba(163,45,45,0.18); --info-soft: rgba(24,95,165,0.15);
    }}
  }}
  * {{ font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif; -webkit-font-smoothing: antialiased; }}
  body {{ background: var(--bg); color: var(--text); margin: 0; padding: 0; }}
  .container {{ max-width: 820px; margin: 0 auto; padding: 48px 24px 64px; }}
  .card {{ background: var(--surface); border: 0.5px solid var(--border); border-radius: 12px; padding: 28px; }}
  .card + .card {{ margin-top: 16px; }}
  .label {{ font-size: 12px; color: var(--text-muted); }}
  .h2 {{ font-size: 17px; font-weight: 500; line-height: 1.4; color: var(--text); }}
  .number-lg {{ font-size: 28px; font-weight: 500; color: var(--text); line-height: 1; }}
  .number-secondary {{ font-size: 14px; color: var(--text-muted); margin-left: 4px; }}
  .body {{ font-size: 15px; line-height: 1.7; color: var(--text); }}
  .body-muted {{ font-size: 14px; line-height: 1.7; color: var(--text-muted); }}
  .meta {{ font-size: 12px; color: var(--text-faint); }}
  .badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 500; }}
  .badge-success {{ background: var(--success-soft); color: var(--success); }}
  .badge-warning {{ background: var(--warning-soft); color: var(--warning); }}
  .badge-danger {{ background: var(--danger-soft); color: var(--danger); }}
  .badge-info {{ background: var(--info-soft); color: var(--accent); }}
  .chart-wrap {{ position: relative; width: 100%; height: 180px; margin: 20px 0; }}
  .action-card {{ background: var(--info-soft); border-radius: 12px; padding: 24px 28px; }}
  .action-card ul {{ margin: 8px 0 0; padding-left: 20px; }}
  .action-card li {{ font-size: 14px; line-height: 1.7; color: var(--text); margin-bottom: 4px; }}
  .footer {{ margin-top: 48px; text-align: center; font-size: 12px; color: var(--text-faint); }}
</style>
</head>
<body>
<div class="container">

  <div class="card" style="border-color: {accent_color};">
    <div class="label" style="margin-bottom: 8px;">{week} · Strompreis-Monitor 2028</div>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;">
      <div class="badge badge-{ampel_class}">{recommendation_label}</div>
      <div class="meta">Composite-Score: {composite:+.2f}</div>
      {fx_meta}
    </div>
    <p class="body" style="margin: 0;">{hero_text}</p>
  </div>

  {kpi_cards}

  <div class="action-card" style="margin-top: 32px;">
    <div class="h2" style="margin: 0 0 4px;">Was diese Woche zu tun ist</div>
    <ul>
      {action_items}
    </ul>
  </div>

  <div class="footer">
    Automatisch generiert am {generated_at} · Datenquelle: energy-charts.info (Fraunhofer ISE) · Wechselkurs: frankfurter.app
  </div>
</div>

<script>
{chart_scripts}
</script>

</body>
</html>
"""


KPI_CARD_TEMPLATE = """
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; flex-wrap: wrap; gap: 8px;">
      <div class="h2">{index}. {title}</div>
      <div class="badge badge-{score_class}">{score_label}</div>
    </div>
    <div class="body-muted" style="margin-bottom: 20px;">{subtitle}</div>

    <div style="display: flex; align-items: baseline; gap: 20px; flex-wrap: wrap;">
      <div class="number-lg">{current_value} {unit}{chf_value}</div>
      <div class="meta">{percentile_text}</div>
      <div class="meta">Trend: {trend}</div>
    </div>

    <div class="chart-wrap">
      <canvas id="chart_{name}" role="img" aria-label="Verlauf {title}"></canvas>
    </div>

    <p class="body" style="margin: 0 0 12px;">
      <strong style="font-weight: 500;">Was zeigt der Chart:</strong> {chart_explanation}
    </p>
    <p class="body" style="margin: 0;">
      <strong style="font-weight: 500;">Warum für 2028 relevant:</strong> {relevance}
    </p>
  </div>
"""


def score_to_class(score: float) -> tuple[str, str]:
    if score < -0.7:
        return "success", "günstig"
    if score < -0.2:
        return "success", "leicht günstig"
    if score < 0.2:
        return "info", "neutral"
    if score < 0.7:
        return "warning", "leicht ungünstig"
    return "danger", "ungünstig"


def ampel_to_class(ampel: str) -> str:
    return {
        "gruen": "success",
        "gelb-gruen": "success",
        "gelb": "warning",
        "rot": "danger",
    }[ampel]


def percentile_to_text(p: float | None) -> str:
    if p is None:
        return "keine Historie"
    if p < 25:
        return f"{p:.0f}. Perzentil (unteres Viertel)"
    if p < 75:
        return f"{p:.0f}. Perzentil (Mittelfeld)"
    return f"{p:.0f}. Perzentil (oberes Viertel)"


def load_meta() -> dict:
    meta_file = DATA_DIR / "meta.json"
    if meta_file.exists():
        with open(meta_file, encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_kpi_cards(kpis: dict, eur_chf_rate: float | None) -> tuple[str, list]:
    cards_html = []
    chart_kpis = []

    for idx, name in enumerate(["ch_spot", "ch_hydro", "fr_nuclear", "de_spot"], start=1):
        kpi = kpis.get(name, {})
        meta = KPI_META[name]

        if kpi.get("current") is None:
            cards_html.append(
                KPI_CARD_TEMPLATE.format(
                    index=idx,
                    title=meta["title"],
                    subtitle=meta["subtitle"],
                    score_class="warning",
                    score_label="Daten fehlen",
                    current_value="–",
                    unit=meta["unit"],
                    chf_value="",
                    percentile_text="keine Daten",
                    trend="unbekannt",
                    name=name,
                    chart_explanation=meta["chart_explanation"],
                    relevance=meta["relevance"],
                )
            )
            continue

        score_class, score_label = score_to_class(kpi["score"])
        formatted_value = meta["format"].format(kpi["current"])

        # CHF-Anzeige fuer Preis-KPIs
        chf_value = ""
        if meta.get("is_price") and eur_chf_rate:
            chf_amount = kpi["current"] * eur_chf_rate
            chf_value = f' <span class="number-secondary">(≈ {chf_amount:.0f} CHF/MWh)</span>'

        cards_html.append(
            KPI_CARD_TEMPLATE.format(
                index=idx,
                title=meta["title"],
                subtitle=meta["subtitle"],
                score_class=score_class,
                score_label=score_label,
                current_value=formatted_value,
                unit=meta["unit"],
                chf_value=chf_value,
                percentile_text=percentile_to_text(kpi.get("percentile")),
                trend=kpi.get("trend", "–"),
                name=name,
                chart_explanation=meta["chart_explanation"],
                relevance=meta["relevance"],
            )
        )
        chart_kpis.append(name)

    return "\n".join(cards_html), chart_kpis


def build_chart_scripts(history: dict, chart_kpis: list[str]) -> str:
    color_map = {
        "ch_spot": "#185FA5",
        "ch_hydro": "#1D9E75",
        "fr_nuclear": "#534AB7",
        "de_spot": "#D85A30",
    }
    scripts = ["""
function mkChart(canvasId, data, color) {
  const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const labels = data.map(p => p.date);
  const values = data.map(p => p.value);
  return new Chart(document.getElementById(canvasId), {
    type: 'line',
    data: { labels, datasets: [{ data: values, borderColor: color, backgroundColor: color + '15', fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: {
        y: { grid: { color: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }, ticks: { color: isDark ? '#9B9B9B' : '#6B6B6B' } },
        x: { grid: { display: false }, ticks: { color: isDark ? '#9B9B9B' : '#6B6B6B', maxRotation: 0, autoSkip: true, maxTicksLimit: 6 } }
      }
    }
  });
}
"""]

    for name in chart_kpis:
        series = history.get(name, [])
        data_js = json.dumps(series)
        scripts.append(f"mkChart('chart_{name}', {data_js}, '{color_map[name]}');")

    return "\n".join(scripts)


def main() -> int:
    with open(DATA_DIR / "current_assessment.json", encoding="utf-8") as f:
        assessment = json.load(f)
    with open(DATA_DIR / "history.json", encoding="utf-8") as f:
        history = json.load(f)
    meta = load_meta()
    eur_chf = meta.get("eur_chf_rate")

    kpi_cards_html, chart_kpis = build_kpi_cards(assessment["kpis"], eur_chf)
    chart_scripts = build_chart_scripts(history, chart_kpis)

    action_items = "\n".join(f"      <li>{action}</li>" for action in assessment["actions"])
    ampel_class = ampel_to_class(assessment["recommendation"]["ampel"])

    fx_meta = ""
    if eur_chf:
        fx_meta = f'<div class="meta">EUR/CHF: {eur_chf:.4f}</div>'

    html = HTML_TEMPLATE.format(
        week=assessment["week"],
        recommendation_label=assessment["recommendation"]["label"],
        ampel_class=ampel_class,
        accent_color=assessment["recommendation"]["color_hex"],
        composite=assessment["composite_score"],
        fx_meta=fx_meta,
        hero_text=assessment["hero_text"],
        kpi_cards=kpi_cards_html,
        action_items=action_items,
        generated_at=datetime.now(timezone.utc).strftime("%d.%m.%Y, %H:%M UTC"),
        chart_scripts=chart_scripts,
    )

    output_file = DOCS_DIR / "index.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard gebaut: {output_file}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
