"""Build an offline chart review from the deterministic sample case.

Run: .venv/bin/python scripts/preview_charts.py
"""
from pathlib import Path
import sys
import os
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

import pandas as pd
import plotly.io as pio
from valuation import plotly_charts as pc
from valuation import plots
from valuation.bridge import valuation_bridge
from valuation.comps import run_comps
from valuation.dcf import run_dcf
from valuation.lbo import run_lbo
from valuation.sample import sample_case
from valuation.surface_workbench import write_dcf_workbench
from valuation.sotp import run_sotp
from valuation.statements import Line, audit, combine, forecast_statements


def figures():
    case = sample_case()
    forecast = forecast_statements(case)
    full = combine(case.history, forecast.statements)
    dcf = run_dcf(case)
    lbo = run_lbo(case)
    sotp = run_sotp(case)
    bridge = valuation_bridge(case)
    unit = case.unit
    last = case.history.income_years()[-1]
    with patch.object(pc, "show", lambda fig: fig):
        yield pc.plot_income_stack(full, unit, history_end=last)
        yield pc.plot_balance_composition(full, unit, history_end=last)
        yield pc.plot_desk_series(full.income.loc[[Line.REVENUE, Line.EBITDA, Line.NET_INCOME]].T,
                                  title="Operating trajectory", ylabel=unit)
        yield pc.plot_surface_panel(*plots.forecast_dcf_surface(case), xlabel="WACC (%)",
                    ylabel="Terminal growth (%)", zlabel="$ / share", title="Gordon DCF · full forecast",
                    x_as_pct=True, y_as_pct=True,
                    mark=(dcf.wacc, case.assumptions.terminal_growth, dcf.gordon_price),
                    reference=case.price, reference_label="Market price")
        yield pc.plot_surface_panel(*plots.forecast_dcf_surface(case, method="exit"), xlabel="WACC (%)",
                    ylabel="Exit EV/EBITDA (x)", zlabel="$ / share", title="Exit-multiple DCF · full forecast",
                    x_as_pct=True, mark=(dcf.wacc, case.assumptions.exit_ev_ebitda, dcf.exit_price),
                    reference=case.price, reference_label="Market price")
        yield pc.plot_cash_bridge(forecast.statements.cashflow, unit)
        yield pc.plot_working_capital(full, unit)
        yield pc.plot_ufcf_waterfall(dcf.gordon_schedule, unit)
        yield pc.plot_dcf_pv_split(dcf)
        row = plots.nearest_label(dcf.gordon_sensitivity.index, dcf.wacc, as_pct=True)
        col = plots.nearest_label(dcf.gordon_sensitivity.columns, case.assumptions.terminal_growth, as_pct=True)
        yield pc.plot_sensitivity_pair(dcf.gordon_sensitivity, "DCF sensitivity", "$ / share", base_row=row, base_col=col)
        yield pc.plot_heatmap(dcf.gordon_sensitivity, "Value versus base", "$ / share", base_row=row, base_col=col, delta=True)
        yield pc.plot_comps_dashboard(run_comps(case), case)
        yield pc.plot_sources_uses(lbo.sources_uses, unit)
        yield pc.plot_debt_stack(lbo.debt_schedule, unit)
        yield pc.plot_returns_bridge(lbo.returns_bridge, unit)
        yield pc.plot_sotp_waterfall(sotp.by_segment, sotp.net_debt, sotp.equity_value, unit)
        segments = sotp.by_segment[sotp.by_segment.enterprise_value > 0]
        yield pc.plot_composition(segments.segment, segments.enterprise_value, title="Segment enterprise value")
        yield pc.plot_football_field(bridge, case.price)
        yield pc.plot_method_bars(bridge, case.price)
        yield pc.plot_audit_heatmap(pd.DataFrame(audit(full)))


def write_gallery(path, figures, *, title, description):
    from html import escape

    rendered, options = [], []
    for i, fig in enumerate(figures):
        name = (fig.layout.title.text or f"Figure {i+1}").split("<br>")[0]
        options.append(f'<option value="chart-{i}">{escape(name)}</option>')
        html = pio.to_html(fig, full_html=False, include_plotlyjs=i == 0, auto_play=False,
                          div_id=f"figure-{i}", config={"displaylogo": False, "responsive": True,
                          "toImageButtonOptions": {"format": "png", "scale": 3}})
        rendered.append(f'<section id="chart-{i}" aria-label="{escape(name)}">{html}</section>')
    path.write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Valuation | Figure review</title>
<style>html{scroll-behavior:smooth}body{margin:0;background:#edf2f6;color:#182b3a;font:15px -apple-system,BlinkMacSystemFont,Arial,sans-serif}
main{max-width:1440px;margin:48px auto;padding:0 24px}header{margin:0 8px 24px}h1{font-size:32px;letter-spacing:-1px;margin:10px 0}
p{color:#647582;line-height:1.6;max-width:1000px}.eyebrow{font-size:11px;letter-spacing:2px}section{background:white;border:1px solid #dce4ea;border-radius:10px;margin-bottom:24px;padding:20px 8px;overflow:hidden;scroll-margin-top:90px}
nav{display:flex;align-items:center;gap:16px;background:#edf2f6f5;position:sticky;top:0;z-index:10;padding:16px 8px;margin-bottom:16px;border-bottom:1px solid #ced8df}
select{border:1px solid #ced8df;background:white;color:#182b3a;border-radius:5px;padding:9px 12px;font:inherit;max-width:70%}a{color:#285f91;text-decoration:none}a:hover{text-decoration:underline}
@media(max-width:800px){main{padding:0 8px;margin-top:24px}section{overflow:auto}.plotly-graph-div{min-width:900px}nav{font-size:12px;gap:8px}}</style>
<main><header><div class="eyebrow">VALUATION / RESEARCH FIGURES</div>'''
        + f'<h1>{escape(title)}</h1><p>{escape(description)}</p></header>'
        + '<nav><label for="jump">Jump to figure</label><select id="jump" onchange="document.getElementById(this.value).scrollIntoView()">'
        + ''.join(options) + '</select><a href="chart_gallery.html">All figures</a><a href="surface_explorer.html">3D explorer</a></nav>'
        + '\n'.join(rendered) + '</main></html>')


def main():
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    charts = list(figures())
    write_gallery(output / "chart_gallery.html", charts, title="The model, made visible.",
                  description="Sample-case figure review. Compare indexed series, inspect valuation ranges and explore assumptions in 3D. All data and chart assets are embedded for offline review.")
    write_dcf_workbench(sample_case(), output / "surface_explorer.html")
    print(f"Wrote {len(charts)} figures and the coordinated DCF workspace to {output}")


if __name__ == "__main__":
    main()
