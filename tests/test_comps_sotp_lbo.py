import math

import pytest

from valuation.case import Peer
from valuation.comps import run_comps
from valuation.lbo import entry_equity_at_target_irr, irr, run_lbo
from valuation.sample import sample_case
from valuation.sotp import run_sotp
from valuation.statements import Line, forecast_statements


def test_irr_known_cash_flows():
    assert irr([-100, 110]) == pytest.approx(0.10)
    assert irr([-100, 0, 121]) == pytest.approx(0.10)
    # 100 r^2 + 140 r - 20 = 0, positive root.
    expected = (-7 + math.sqrt(69)) / 10
    assert irr([-100, 60, 60]) == pytest.approx(expected)


def test_comps_keep_the_outlier_and_exclude_the_subject():
    case = sample_case()
    case.peers = [
        Peer("A", 1.0, 10.0, 10.0, True),
        Peer("B", 1.0, 12.0, 10.0, True),
        Peer("C", 1.0, 14.0, 10.0, True),
        Peer("D", 1.0, 100.0, 10.0, True),
    ]
    result = run_comps(case)
    assert result.stats.loc["median", "ev_ebitda"] == pytest.approx(13)
    assert result.stats.loc["mean", "ev_ebitda"] == pytest.approx(34)
    assert result.stats.loc["max", "ev_ebitda"] == pytest.approx(100)
    ebitda = float(result.subject.loc[0, "ebitda"])
    net_debt = float(result.subject.loc[0, "net_debt"])
    implied = result.implied.set_index("method").loc["EV/EBITDA"]
    assert implied["price_mid"] == pytest.approx((13 * ebitda - net_debt) / case.shares)
    assert "Northbridge" not in set(result.peers["name"])


def test_sotp_discount_and_sample_tie_out():
    case = sample_case()
    for basis in ("ltm", "forward"):
        result = run_sotp(case, basis=basis)
        assert result.ebitda_gap == pytest.approx(0, abs=1e-6)
        assert result.enterprise_value_after_discount == pytest.approx(result.enterprise_value * 0.90)
        assert result.equity_value == pytest.approx(result.enterprise_value_after_discount - result.net_debt)

    case.segments = []
    empty = run_sotp(case, basis="ltm")
    assert math.isnan(empty.price)
    assert empty.warnings


def test_lbo_sources_bridge_and_operating_ebit():
    case = sample_case()
    result = run_lbo(case)
    uses = result.sources_uses.loc[result.sources_uses["item"] == "Total uses", "amount"].iloc[0]
    sources = result.sources_uses.loc[result.sources_uses["item"] == "Total sources", "amount"].iloc[0]
    assert uses == pytest.approx(sources)
    assert result.sponsor_equity > 0
    assert result.converged
    bridge = result.returns_bridge.set_index("item")["amount"]
    rebuilt = (
        bridge["Entry firm equity"]
        + bridge["EBITDA growth at the exit multiple"]
        + bridge["Multiple change on entry EBITDA"]
        + bridge["Deleveraging"]
    )
    assert rebuilt == pytest.approx(bridge["Exit firm equity"])
    assert bridge["Entry firm equity"] + bridge["Fees, outside the operating bridge"] == pytest.approx(
        bridge["Sponsor equity invested"]
    )
    assert result.moic == pytest.approx(result.exit_equity / result.sponsor_equity)
    assert result.irr is not None

    corporate = forecast_statements(case)
    assert result.statements.income.loc[Line.EBIT].tolist() == pytest.approx(
        corporate.statements.income.loc[Line.EBIT].tolist()
    )
    assert result.statements.income.loc[Line.NET_INCOME].tolist() != pytest.approx(
        corporate.statements.income.loc[Line.NET_INCOME].tolist()
    )


def test_lbo_target_irr_solver():
    case = sample_case()
    bid = entry_equity_at_target_irr(case)
    assert bid is not None and bid > 0
    priced = run_lbo(case, entry_equity=bid)
    assert priced.irr == pytest.approx(case.assumptions.lbo.target_irr, abs=1e-3)
