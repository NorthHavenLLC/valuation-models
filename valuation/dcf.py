"""Unlevered DCF.

Free cash flow is EBIT after tax at the statutory rate, plus D&A, minus capex,
minus the increase in operating working capital. The interest tax shield is in
WACC, not in the cash flows. Forecast cash that piles up on the balance sheet
is not added again: enterprise value already contains those cash flows, and
net debt is the latest balance sheet only.

Gordon terminal value is next year's free cash flow divided by WACC minus
growth. The exit multiple is applied to the final forecast year's EBITDA.
Those are different conventions and they will not agree.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from valuation.case import Case
from valuation.statements import Line, forecast_statements, last_actual_year

def cost_of_equity(case: Case) -> float:
    assumptions = case.assumptions
    return assumptions.risk_free + assumptions.beta * assumptions.equity_risk_premium


def after_tax_cost_of_debt(case: Case) -> float:
    return case.assumptions.pretax_cost_of_debt * (1.0 - case.assumptions.tax_rate)


def capital_structure(case: Case) -> tuple[float, float, str]:
    weight = case.assumptions.target_debt_weight
    if weight is not None:
        return 1.0 - weight, weight, "target capital structure set on the case"
    if case.price is None:
        return 0.75, 0.25, "price is missing; used a 25% debt weight"
    equity = case.price * case.shares
    year = last_actual_year(case.history)
    debt = max(float(case.history.balance.loc[Line.DEBT, year]), 0.0)
    total = equity + debt
    if total <= 0:
        return 1.0, 0.0, "capital is non-positive; WACC is the cost of equity"
    return (
        equity / total,
        debt / total,
        "book debt and the entered price; the price and WACC are not iterated to a fixed point",
    )


def wacc_components(case: Case) -> tuple[float, float, float, float, float, str]:
    ke = cost_of_equity(case)
    kd = after_tax_cost_of_debt(case)
    equity_weight, debt_weight, note = capital_structure(case)
    return equity_weight * ke + debt_weight * kd, ke, kd, equity_weight, debt_weight, note


def net_debt(case: Case) -> float:
    """Latest balance sheet only. Forecast cash is already inside free cash flow."""
    year = last_actual_year(case.history)
    balance = case.history.balance
    return float(balance.loc[Line.DEBT, year]) - float(balance.loc[Line.CASH, year])


def gordon_terminal_value(final_fcf: float, growth: float, rate: float) -> float:
    if rate <= growth:
        raise ValueError(
            f"WACC ({rate:.2%}) must exceed terminal growth ({growth:.2%}) "
            "for a Gordon terminal value."
        )
    return final_fcf * (1.0 + growth) / (rate - growth)


def present_value(cashflows: list[float], rate: float, mid_year: bool = False) -> float:
    total = 0.0
    for t, cashflow in enumerate(cashflows, start=1):
        exponent = t - 0.5 if mid_year else float(t)
        total += cashflow / (1.0 + rate) ** exponent
    return total


def discount_factor(t: int, rate: float, mid_year: bool) -> float:
    exponent = t - 0.5 if mid_year else float(t)
    return 1.0 / (1.0 + rate) ** exponent


def unlevered_fcf(case: Case, income: pd.DataFrame, cashflow: pd.DataFrame) -> pd.Series:
    tax_rate = case.assumptions.tax_rate
    values: dict[int, float] = {}
    for year in [int(c) for c in income.columns]:
        ebit = float(income.loc[Line.EBIT, year])
        da = float(income.loc[Line.DA, year])
        capex = float(cashflow.loc[Line.CAPEX, year])
        delta_nwc = (
            float(cashflow.loc[Line.INCREASE_AR, year])
            + float(cashflow.loc[Line.INCREASE_INV, year])
            - float(cashflow.loc[Line.INCREASE_AP, year])
        )
        values[year] = ebit * (1.0 - tax_rate) + da - capex - delta_nwc
    return pd.Series(values, dtype=float)


def _schedule(years: list[int], flows: list[float], terminal: float, rate: float, mid_year: bool) -> pd.DataFrame:
    rows: dict[str, dict[str, float]] = {}
    for t, (year, flow) in enumerate(zip(years, flows), start=1):
        factor = discount_factor(t, rate, mid_year)
        rows[str(year)] = {
            "Cash flow": flow,
            "Discount factor": factor,
            "Present value": flow * factor,
        }
    factor = discount_factor(len(years), rate, mid_year)
    rows["Terminal value"] = {
        "Cash flow": terminal,
        "Discount factor": factor,
        "Present value": terminal * factor,
    }
    return pd.DataFrame.from_dict(rows, orient="index")


def _price_grid(
    flows: list[float],
    final_ebitda: float,
    net: float,
    shares: float,
    rate_grid: list[float],
    growth_grid: list[float],
    multiples: list[float],
    mid_year: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    gordon = pd.DataFrame(index=[f"{rate:.2%}" for rate in rate_grid], columns=[f"{g:.2%}" for g in growth_grid], dtype=float)
    exit_grid = pd.DataFrame(index=[f"{rate:.2%}" for rate in rate_grid], columns=[f"{m:.1f}x" for m in multiples], dtype=float)
    for rate in rate_grid:
        for growth in growth_grid:
            label_r, label_g = f"{rate:.2%}", f"{growth:.2%}"
            if rate <= growth:
                gordon.loc[label_r, label_g] = float("nan")
                continue
            tv = gordon_terminal_value(flows[-1], growth, rate)
            ev = present_value(flows, rate, mid_year) + tv * discount_factor(len(flows), rate, mid_year)
            gordon.loc[label_r, label_g] = (ev - net) / shares
        for multiple in multiples:
            tv = final_ebitda * multiple
            ev = present_value(flows, rate, mid_year) + tv * discount_factor(len(flows), rate, mid_year)
            exit_grid.loc[f"{rate:.2%}", f"{multiple:.1f}x"] = (ev - net) / shares
    return gordon, exit_grid


@dataclass
class DcfResult:
    gordon_schedule: pd.DataFrame
    exit_schedule: pd.DataFrame
    wacc: float
    cost_of_equity: float
    after_tax_cost_of_debt: float
    equity_weight: float
    debt_weight: float
    weight_note: str
    gordon_terminal_value: float
    exit_terminal_value: float
    gordon_enterprise_value: float
    exit_enterprise_value: float
    net_debt: float
    gordon_equity_value: float
    exit_equity_value: float
    gordon_price: float
    exit_price: float
    gordon_tv_share: float
    exit_tv_share: float
    gordon_sensitivity: pd.DataFrame
    exit_sensitivity: pd.DataFrame
    warnings: list[str]


def run_dcf(case: Case, interest: str = "beginning") -> DcfResult:
    forecast = forecast_statements(case, interest=interest)  # type: ignore[arg-type]
    flows_s = unlevered_fcf(case, forecast.statements.income, forecast.statements.cashflow)
    years = [int(y) for y in flows_s.index]
    flows = [float(flows_s.loc[y]) for y in years]
    ebitda = [float(forecast.statements.income.loc[Line.EBITDA, y]) for y in years]
    rate, ke, kd, we, wd, note = wacc_components(case)
    growth = case.assumptions.terminal_growth
    tv_gordon = gordon_terminal_value(flows[-1], growth, rate)
    tv_exit = ebitda[-1] * case.assumptions.exit_ev_ebitda
    mid = case.assumptions.mid_year
    final_factor = discount_factor(len(flows), rate, mid)
    pv_flows = present_value(flows, rate, mid)
    gordon_ev = pv_flows + tv_gordon * final_factor
    exit_ev = pv_flows + tv_exit * final_factor
    debt = net_debt(case)
    warnings: list[str] = []
    year = last_actual_year(case.history)
    other_assets = float(case.history.balance.loc[Line.OTHER_ASSETS, year])
    other_liab = float(case.history.balance.loc[Line.OTHER_LIAB, year])
    if abs(other_assets) > 1 or abs(other_liab) > 1:
        warnings.append(
            f"Other assets ({other_assets:,.1f}) and other liabilities ({other_liab:,.1f}) "
            "are left out of net debt. They are not treated as cash."
        )
    if not forecast.converged:
        warnings.append("Average-debt interest did not converge. Free cash flow is unlevered, so DCF cash flows are unaffected.")
    rate_grid = [rate + step for step in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    growth_grid = [0.0, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035]
    multiples = [6.0, 8.0, 10.0, 12.0, 14.0]
    gordon_sens, exit_sens = _price_grid(
        flows, ebitda[-1], debt, case.shares, rate_grid, growth_grid, multiples, mid
    )
    return DcfResult(
        gordon_schedule=_schedule(years, flows, tv_gordon, rate, mid),
        exit_schedule=_schedule(years, flows, tv_exit, rate, mid),
        wacc=rate,
        cost_of_equity=ke,
        after_tax_cost_of_debt=kd,
        equity_weight=we,
        debt_weight=wd,
        weight_note=note,
        gordon_terminal_value=tv_gordon,
        exit_terminal_value=tv_exit,
        gordon_enterprise_value=gordon_ev,
        exit_enterprise_value=exit_ev,
        net_debt=debt,
        gordon_equity_value=gordon_ev - debt,
        exit_equity_value=exit_ev - debt,
        gordon_price=(gordon_ev - debt) / case.shares,
        exit_price=(exit_ev - debt) / case.shares,
        gordon_tv_share=(tv_gordon * final_factor) / gordon_ev if gordon_ev else float("nan"),
        exit_tv_share=(tv_exit * final_factor) / exit_ev if exit_ev else float("nan"),
        gordon_sensitivity=gordon_sens,
        exit_sensitivity=exit_sens,
        warnings=warnings,
    )
