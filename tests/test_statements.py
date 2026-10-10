import pytest

from valuation.case import TOL
from valuation.dcf import unlevered_fcf
from valuation.sample import sample_case
from valuation.statements import (
    CorporatePolicy,
    Line,
    OperatingDrivers,
    Stocks,
    audit,
    forecast_statements,
    identity_failures,
    max_abs_gap,
    project,
)


def _opening() -> Stocks:
    return Stocks(
        cash=100.0,
        ar=0.0,
        inventory=0.0,
        ppe=100.0,
        other_assets=0.0,
        ap=0.0,
        debt=100.0,
        other_liabilities=0.0,
        equity=100.0,
    )


def _drivers(**overrides) -> OperatingDrivers:
    base = dict(
        year=2021,
        revenue=100.0,
        gross_margin=0.5,
        opex_pct_sales=0.2,
        da_pct_begin_ppe=0.1,
        capex_pct_sales=0.1,
        tax_rate=0.25,
        dso=0.0,
        dio=0.0,
        dpo=0.0,
    )
    base.update(overrides)
    return OperatingDrivers(**base)


def _policy(**overrides) -> CorporatePolicy:
    base = dict(interest_rate=0.10, dividend_payout=0.0, minimum_cash=0.0, debt_paydown=0.0)
    base.update(overrides)
    return CorporatePolicy(**base)


def test_beginning_interest_matches_a_hand_calc():
    built = project(2020, _opening(), [(_drivers(), _policy())], interest="beginning")
    income = built.statements.income
    balance = built.statements.balance
    assert income.loc[Line.EBIT, 2021] == pytest.approx(20)
    assert income.loc[Line.INTEREST, 2021] == pytest.approx(10)
    assert income.loc[Line.NET_INCOME, 2021] == pytest.approx(7.5)
    assert balance.loc[Line.CASH, 2021] == pytest.approx(107.5)
    assert balance.loc[Line.DEBT, 2021] == pytest.approx(100)
    assert balance.loc[Line.EQUITY, 2021] == pytest.approx(107.5)
    assert max_abs_gap(audit(built.statements)) == pytest.approx(0, abs=1e-9)


def test_draw_to_minimum_cash_balances():
    built = project(
        2020,
        _opening(),
        [(_drivers(), _policy(minimum_cash=200))],
        interest="beginning",
    )
    balance = built.statements.balance
    cashflow = built.statements.cashflow
    assert balance.loc[Line.CASH, 2021] == pytest.approx(200)
    assert cashflow.loc[Line.DEBT_DRAW, 2021] == pytest.approx(92.5)
    assert balance.loc[Line.DEBT, 2021] == pytest.approx(192.5)
    assert max_abs_gap(audit(built.statements)) == pytest.approx(0, abs=1e-9)


def test_average_interest_with_paydown_matches_a_hand_calc():
    built = project(
        2020,
        _opening(),
        [(_drivers(), _policy(debt_paydown=40))],
        interest="average",
    )
    assert built.converged
    income = built.statements.income
    balance = built.statements.balance
    # End debt is 60, so average debt is 80 and interest is 8. Paydown does not depend on interest.
    assert income.loc[Line.INTEREST, 2021] == pytest.approx(8)
    assert income.loc[Line.NET_INCOME, 2021] == pytest.approx(9)
    assert balance.loc[Line.CASH, 2021] == pytest.approx(69)
    assert balance.loc[Line.DEBT, 2021] == pytest.approx(60)
    assert balance.loc[Line.EQUITY, 2021] == pytest.approx(109)
    assert max_abs_gap(audit(built.statements)) == pytest.approx(0, abs=1e-9)


def test_average_interest_still_balances_when_the_revolver_draws():
    built = project(
        2020,
        _opening(),
        [(_drivers(), _policy(minimum_cash=200))],
        interest="average",
    )
    assert built.converged
    assert built.statements.balance.loc[Line.CASH, 2021] == pytest.approx(200)
    assert max_abs_gap(audit(built.statements)) < 1e-8


def test_unlevered_fcf_uses_ebit_not_levered_tax():
    built = project(2020, _opening(), [(_drivers(), _policy())], interest="beginning")
    case = sample_case()
    # The tiny case and the sample share a 25% tax rate.
    flows = unlevered_fcf(case, built.statements.income, built.statements.cashflow)
    # 20 * (1 - 0.25) + 10 - 10 - 0
    assert flows.loc[2021] == pytest.approx(15)


def test_sample_history_and_forecast_tie():
    case = sample_case()
    assert identity_failures(audit(case.history), tol=TOL).empty
    forecast = forecast_statements(case, interest="beginning")
    assert forecast.converged
    assert identity_failures(audit(forecast.statements), tol=TOL).empty
    assert forecast.statements.cashflow.loc[Line.DEBT_DRAW].sum() == pytest.approx(0)
    last = case.history.income_years()[-1]
    assert forecast.statements.income_years()[0] == last + 1
    growth = case.assumptions.revenue_growth[0]
    assert forecast.statements.income.loc[Line.REVENUE, last + 1] == pytest.approx(
        case.history.income.loc[Line.REVENUE, last] * (1 + growth)
    )


def test_unlevered_fcf_does_not_depend_on_the_interest_circularity():
    case = sample_case()
    beginning = forecast_statements(case, interest="beginning")
    average = forecast_statements(case, interest="average")
    assert average.converged
    left = unlevered_fcf(case, beginning.statements.income, beginning.statements.cashflow)
    right = unlevered_fcf(case, average.statements.income, average.statements.cashflow)
    assert left.tolist() == pytest.approx(right.tolist())
    # Ending debt is below opening debt, so average-debt interest is lower.
    assert (
        beginning.statements.income.loc[Line.INTEREST] - average.statements.income.loc[Line.INTEREST]
    ).abs().sum() > 0
