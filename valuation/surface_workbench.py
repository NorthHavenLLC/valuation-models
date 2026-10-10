"""Offline, coordinated DCF scenario workspace for notebooks and browser review."""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

from valuation.case import Case
from valuation.dcf import net_debt, unlevered_fcf, wacc_components
from valuation.statements import Line, forecast_statements

ASSETS = Path(__file__).with_name("assets")


def dcf_workbench_payload(case: Case) -> dict:
    forecast = forecast_statements(case).statements
    flows = unlevered_fcf(case, forecast.income, forecast.cashflow)
    rate = wacc_components(case)[0]
    growth = float(case.assumptions.terminal_growth)
    multiple = float(case.assumptions.exit_ev_ebitda)
    payload = {
        "name": case.name, "currency": case.currency, "unit": case.unit,
        "flows": flows.tolist(), "years": [int(y) for y in flows.index],
        "finalEbitda": float(forecast.income.loc[Line.EBITDA].iloc[-1]),
        "netDebt": net_debt(case), "shares": float(case.shares),
        "midYear": case.assumptions.mid_year,
        "market": float(case.price) if case.price is not None and math.isfinite(case.price) else None,
        "base": {"rate": rate, "gordon": growth, "exit": multiple},
        "bounds": {"rate": [max(-.99, rate-.03), rate+.03],
                   "gordon": [growth-.02, growth+.02], "exit": [multiple-4, multiple+4]},
    }
    numbers = [*payload["flows"], payload["finalEbitda"], payload["netDebt"], payload["shares"], rate, growth, multiple]
    if not payload["flows"] or not all(math.isfinite(v) for v in numbers) or rate <= -1 or case.shares <= 0:
        raise ValueError("The workspace requires finite forecast inputs, positive shares and WACC above -100%")
    payload["bounds"]["rate"][0] = min(rate, payload["bounds"]["rate"][0])
    return payload


def dcf_workbench_html(case: Case) -> str:
    """Return a self-contained document with embedded data, Plotly and UI assets."""
    from plotly.offline import get_plotlyjs

    payload = json.dumps(dcf_workbench_payload(case), allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = (ASSETS / "dcf_workbench.html").read_text()
    return (template.replace("__STYLE__", (ASSETS / "dcf_workbench.css").read_text())
            .replace("__PLOTLY__", get_plotlyjs())
            .replace("__MODEL__", (ASSETS / "dcf_model.js").read_text())
            .replace("__CONTROLLER__", (ASSETS / "dcf_workbench.js").read_text())
            .replace("__DATA__", payload))


def write_dcf_workbench(case: Case, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dcf_workbench_html(case))
    return path


def show_dcf_workbench(case: Case) -> None:
    """Display the same offline workspace inside a trusted notebook output."""
    from IPython.display import HTML, display

    doc = html.escape(dcf_workbench_html(case), quote=True)
    display(HTML(f'<iframe title="DCF scenario workspace" srcdoc="{doc}" '
                 'sandbox="allow-scripts allow-downloads" '
                 'style="width:100%;height:1550px;border:0;border-radius:12px"></iframe>'))
