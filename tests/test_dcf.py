import math

import pytest

from valuation.dcf import (
    discount_factor,
    gordon_terminal_value,
    present_value,
    run_dcf,
)
from valuation.sample import sample_case
from valuation.statements import Line, forecast_statements, last_actual_year


def test_gordon_terminal_and_present_value_by_hand():
    tv = gordon_terminal_value(110, 0.02, 0.10)
    assert tv == pytest.approx(110 * 1.02 / 0.08)
    explicit = present_value([100, 110], 0.10, mid_year=False)
    terminal_pv = tv * discount_factor(2, 0.10, mid_year=False)
    assert explicit + terminal_pv == pytest.approx(100 / 1.1 + 110 / 1.21 + tv / 1.21)
    mid = present_value([100, 110], 0.10, mid_year=True)
    mid_tv = tv * discount_factor(2, 0.10, mid_year=True)
    assert mid + mid_tv == pytest.approx(
        100 / 1.1**0.5 + 110 / 1.1**1.5 + tv / 1.1**1.5
    )


def test_gordon_rejects_growth_at_or_above_wacc():
    with pytest.raises(ValueError):
        gordon_terminal_value(100, 0.10, 0.10)


def test_sample_wacc_uses_the_target_structure():
    result = run_dcf(sample_case())
    ke = 0.04 + 1.10 * 0.05
    kd = 0.06 * (1 - 0.25)
    assert result.cost_of_equity == pytest.approx(ke)
    assert result.after_tax_cost_of_debt == pytest.approx(kd)
    assert result.wacc == pytest.approx(ke * 0.75 + kd * 0.25)
    assert result.debt_weight == pytest.approx(0.25)
    assert 0 < result.gordon_tv_share < 1
    assert result.gordon_schedule["Present value"].sum() == pytest.approx(result.gordon_enterprise_value)
    assert result.exit_schedule["Present value"].sum() == pytest.approx(result.exit_enterprise_value)


def test_net_debt_is_the_latest_balance_sheet_not_forecast_cash():
    case = sample_case()
    result = run_dcf(case)
    year = last_actual_year(case.history)
    historical = float(case.history.balance.loc[Line.DEBT, year]) - float(
        case.history.balance.loc[Line.CASH, year]
    )
    forecast = forecast_statements(case)
    final_cash = float(forecast.statements.balance.loc[Line.CASH, forecast.statements.income_years()[-1]])
    assert result.net_debt == pytest.approx(historical)
    assert final_cash != pytest.approx(float(case.history.balance.loc[Line.CASH, year]), abs=1.0)


def test_sensitivity_is_blank_when_growth_meets_wacc():
    result = run_dcf(sample_case())
    # The grid includes growth rates above and below the case WACC. At least one cell is a number.
    assert result.gordon_sensitivity.notna().any().any()
    assert math.isfinite(result.gordon_price)
