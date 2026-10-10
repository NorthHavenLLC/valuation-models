import pandas as pd
import pytest

from valuation.load import load_case, map_reported
from valuation.statements import Line, audit


def _frame(index, rows):
    columns = {pd.Timestamp(f"{year}-12-31"): values for year, values in rows.items()}
    return pd.DataFrame(columns, index=index)


def test_mapper_does_not_call_a_plug_cash():
    income = _frame(
        ["Total Revenue", "Gross Profit", "Operating Income", "Interest Expense", "Tax Provision", "Net Income"],
        {
            2023: [1000e6, 400e6, 200e6, -20e6, 40e6, 100e6],
            2024: [1100e6, 440e6, 220e6, -20e6, 45e6, 130e6],
        },
    )
    balance = _frame(
        [
            "Cash And Cash Equivalents",
            "Accounts Receivable",
            "Inventory",
            "Net PPE",
            "Total Assets",
            "Accounts Payable",
            "Total Debt",
            "Stockholders Equity",
            "Total Liabilities Net Minority Interest",
        ],
        {
            2023: [50e6, 20e6, 10e6, 100e6, 200e6, 15e6, 40e6, 130e6, 70e6],
            # PP&E 125 does not roll from 100 + capex 20 - DA 10. Cash stays 60.
            2024: [60e6, 22e6, 11e6, 125e6, 230e6, 16e6, 35e6, 150e6, 80e6],
        },
    )
    cashflow = _frame(
        [
            "Operating Cash Flow",
            "Investing Cash Flow",
            "Financing Cash Flow",
            "Capital Expenditure",
            "Depreciation And Amortization",
            "Common Stock Dividend Paid",
        ],
        {
            2023: [30e6, -15e6, -10e6, -12e6, 8e6, -3e6],
            # Flows sum to 7; cash increased by 10. Gap of 3 must survive.
            2024: [40e6, -25e6, -8e6, -20e6, 10e6, -4e6],
        },
    )
    case = map_reported(
        income,
        balance,
        cashflow,
        ticker="TEST",
        price=20.0,
        shares=10_000_000,
        beta=1.1,
        currency="USD",
        price_as_of="2026-10-08",
        name="Test Co",
    )
    assert case.synthetic is False
    assert case.shares == pytest.approx(10)
    assert case.history.balance.loc[Line.CASH, 2024] == pytest.approx(60)
    assert case.history.income.loc[Line.INTEREST, 2024] == pytest.approx(20)
    other_assets = float(case.history.balance.loc[Line.OTHER_ASSETS, 2024])
    assert other_assets != pytest.approx(0)
    assert other_assets != pytest.approx(60)
    text = " ".join(case.warnings).lower()
    assert "not cash" in text
    assert "cash was not adjusted" in text
    gaps = audit(case.history)
    assert gaps.loc["cash_rollforward_gap", 2024] == pytest.approx(3)
    assert gaps.loc["ppe_rollforward_gap", 2024] == pytest.approx(15)
    # Buybacks and other equity movements are not stuffed into cash or into net income.
    assert abs(gaps.loc["equity_rollforward_gap", 2024]) > 1
    assert case.history.income_years() == [2024]
    assert 2023 in case.history.balance_years()


def test_sample_load_does_not_mix_live_peers():
    case = load_case(None, peers=["AAPL"])
    assert case.synthetic
    assert all(peer.synthetic for peer in case.peers)
    assert "AAPL" not in {peer.ticker for peer in case.peers}
    assert any("synthetic" in warning.lower() for warning in case.warnings)


def test_bridge_on_the_sample_is_finite():
    from valuation.bridge import valuation_bridge

    bridge = valuation_bridge(load_case())
    assert set(bridge["method"]) >= {
        "Market price",
        "DCF, Gordon growth",
        "DCF, exit multiple",
        "Sum of the parts",
    }
    assert bridge["mid"].notna().all()
    assert (bridge["low"] <= bridge["mid"]).all()
    assert (bridge["mid"] <= bridge["high"]).all()
