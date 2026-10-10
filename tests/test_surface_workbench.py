import json
from dataclasses import replace
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from valuation.dcf import run_dcf, present_value, discount_factor
from valuation.sample import sample_case
from valuation.surface_workbench import dcf_workbench_payload, dcf_workbench_html

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def js_run(code, data):
    if not NODE:
        pytest.skip("Node is needed for JavaScript model checks")
    source = "const M = require('./valuation/assets/dcf_model.js');const data=JSON.parse(require('fs').readFileSync(0,'utf8'));" + code
    result = subprocess.run([NODE, "-e", source], input=json.dumps(data), text=True,
                            cwd=ROOT, capture_output=True, check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize("mid_year", [False, True])
def test_browser_model_reconciles_to_python_forecast_dcf(mid_year):
    case = sample_case()
    case.assumptions = replace(case.assumptions, mid_year=mid_year, exit_ev_ebitda=24.)
    payload = dcf_workbench_payload(case)
    actual = js_run("console.log(JSON.stringify(['gordon','exit'].map(m=>M.evaluate(data,m,data.base.rate,data.base[m]))));", payload)
    expected = run_dcf(case)
    assert actual[0]["price"] == pytest.approx(expected.gordon_price)
    assert actual[1]["price"] == pytest.approx(expected.exit_price)
    assert actual[0]["terminalShare"] == pytest.approx(expected.gordon_tv_share)
    assert actual[1]["terminalPV"] == pytest.approx(expected.exit_schedule.loc["Terminal value", "Present value"])
    for result in actual:
        assert result["explicitPerShare"] + result["terminalPerShare"] - result["debtPerShare"] == pytest.approx(result["price"])


def test_browser_model_matches_off_base_scenarios():
    model = dcf_workbench_payload(sample_case())
    queries = [["gordon", .11, .035], ["gordon", .06, -.01], ["exit", .095, 13.5], ["exit", .07, 5.]]
    values = js_run("console.log(JSON.stringify(data.queries.map(q=>M.evaluate(data.model,...q))));", {"model": model, "queries": queries})
    for query, value in zip(queries, values):
        method, rate, terminal = query
        tv = model["flows"][-1]*(1+terminal)/(rate-terminal) if method == "gordon" else model["finalEbitda"]*terminal
        price = (present_value(model["flows"], rate, model["midYear"]) + tv*discount_factor(len(model["flows"]), rate, model["midYear"]) - model["netDebt"])/model["shares"]
        assert value["price"] == pytest.approx(price)


def test_inverse_solvers_reach_target_without_bridging_undefined_regions():
    model = dcf_workbench_payload(sample_case())
    result = js_run('''
      const rates=M.roots(r=>M.evaluate(data,'gordon',r,.025)?.price,22,data.bounds.rate);
      const terminals=['gordon','exit'].map(m=>M.targetTerminal(data,m,data.base.rate,22));
      console.log(JSON.stringify({rates,terminalPrices:terminals.map((v,i)=>M.evaluate(data,i?'exit':'gordon',data.base.rate,v).price),
        prices:rates.map(r=>M.evaluate(data,'gordon',r,.025).price),
        invalid:M.evaluate(data,'gordon',.02,.03),
        pole:M.roots(x=>x===0?null:1/x,0,[-1,1]),
        two:M.roots(x=>x*x,1,[-2,2]),
        missing:M.roots(x=>null,22,[0,1])}));
    ''', model)
    assert len(result["rates"]) >= 1
    np.testing.assert_allclose(result["prices"], 22, rtol=1e-7)
    np.testing.assert_allclose(result["terminalPrices"], 22, rtol=1e-7)
    assert result["invalid"] is None
    assert result["pole"] == []
    assert result["missing"] == []
    np.testing.assert_allclose(result["two"], [-1, 1], atol=1e-6)


def test_workbench_export_is_offline_and_escapes_case_names():
    case = sample_case()
    case.name = '</script><script>alert("bad")</script>'
    doc = dcf_workbench_html(case)
    assert case.name not in doc
    assert '\\u003c/script\\u003e' in doc
    assert '__CONTROLLER__' not in doc and '__DATA__' not in doc
    assert 'id="model-data"' in doc and 'Plotly.react' in doc
    assert '<script src=' not in doc
    assert 'Target-price map' in doc


def test_workbench_controller_coordinates_selection_solver_and_pins():
    if not NODE:
        pytest.skip("Node is needed for JavaScript controller checks")
    result = subprocess.run([NODE, str(ROOT / 'tests/workbench_controller.cjs')],
                            input=json.dumps(dcf_workbench_payload(sample_case())), text=True,
                            cwd=ROOT, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
