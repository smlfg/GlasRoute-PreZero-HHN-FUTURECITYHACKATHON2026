"""Render the three cadence views as standalone HTML files (offline, no server).

Use case: proof that the views work offline on their own and at the minimum
width of 800 px — the standalone files carry their own CSS and the (precomputed)
payload, so they need neither the full website nor a running server.

    PYTHONPATH=src python scripts/render_cadence_views.py --date 2026-04-15

Writes ``docs/ui-cadence/ansicht_1_container.html`` (and _2, _3) plus the
screenshots into ``docs/ui-cadence/``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402

from prezero import ui_cadence  # noqa: E402
from prezero.ui_cadence_assets import CSS as CADENCE_CSS  # noqa: E402
from prezero.ui_cadence_js import JS as CADENCE_JS  # noqa: E402

#: Minimum width the views must work at (task requirement).
VIEWPORT_WIDTH_PX = 800


def _standalone_page(title: str, body: str, body_class: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --surface: #ffffff;
      --border: #cbd5e1;
      --text: #0f172a;
      --muted: #475569;
      --accent: #1d4ed8;
      --accent-soft: #eff6ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    .cadence-frame {{
      width: {VIEWPORT_WIDTH_PX}px;
      margin: 0 auto;
      padding: 16px 20px 40px;
    }}
    .section-head h2 {{ margin: 0 0 4px; font-size: 18px; }}
    .muted {{ margin: 0 0 14px; color: var(--muted); font-size: 13px; }}
    .kpi-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      min-width: 0;
    }}
    .card .label {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
    .card .value {{ font-size: 20px; font-weight: 700; }}
    .card .sub {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
    .primary-btn {{
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #ffffff;
      padding: 8px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 9px;
      border-radius: 999px;
      background: #e2e8f0;
      color: #334155;
      font-size: 12px;
      font-weight: 700;
    }}
    .badge.pending {{ background: #fef3c7; color: #92400e; }}
    .badge.ok {{ background: #dcfce7; color: #166534; }}
    .map-wrap {{ margin-bottom: 18px; }}
{CADENCE_CSS}
  </style>
</head>
<body class="{body_class}">
  <div class="cadence-frame">
{body}
  </div>
  <script>
{CADENCE_JS}
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the cadence views standalone.")
    parser.add_argument("--date", default="2026-04-15", help="Stichtag (YYYY-MM-DD).")
    parser.add_argument(
        "--readings", default="data/processed/cleaned_readings.csv", help="Cleaned readings."
    )
    parser.add_argument(
        "--locations", default="data/external/locations.csv", help="Locations CSV."
    )
    parser.add_argument(
        "--scenarios-dir",
        default="data/outputs/scenarios",
        help="Directory with the scenario output of the model lane.",
    )
    parser.add_argument(
        "--out-dir", default="docs/ui-cadence", help="Directory for the standalone views."
    )
    args = parser.parse_args()

    readings = pd.read_csv(args.readings, parse_dates=["date"])

    sections = ui_cadence.build_cadence_sections(
        readings,
        args.date,
        scenario_dir=args.scenarios_dir,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = {
        "ansicht_1_container.html": ("Container & Takt", sections["list"]),
        "ansicht_2_detail.html": ("Container im Detail", sections["detail"]),
        "ansicht_3_woche.html": ("Diese Woche", sections["week"]),
        "ansicht_4_szenarien.html": ("Szenarien (Jahr)", sections["scenarios"]),
    }
    for name, (title, body) in pages.items():
        page = _standalone_page(f"GlasRoute — {title}", body)
        (out_dir / name).write_text(page, encoding="utf-8")
        print(f"Written: {out_dir / name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
