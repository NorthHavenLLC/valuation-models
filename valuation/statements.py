"""Three-statement projection.

The sample history is produced by this same engine, so the links are
identities. A live filing is mapped elsewhere and will usually not satisfy
them. The forecast that starts from its latest balance sheet should.

Working capital uses a 365-day year. Tax is a full shield on EBT, including
a benefit when EBT is negative. There is no NOL limit.

Interest is charged on beginning debt, or solved on the average of beginning
and ending debt. Average mode is a one-dimensional fixed point: interest
changes net income, which can change the cash draw, which changes ending debt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from valuation.case import TOL, Case, Statements

DAYS = 365.0
InterestMode = Literal["beginning", "average"]


class Line:
    REVENUE = "Revenue"
    COGS = "COGS"
    GROSS_PROFIT = "Gross profit"
    OPEX = "Operating expenses"
    EBITDA = "EBITDA"
    DA = "D&A"
    EBIT = "EBIT"
    INTEREST = "Interest expense"
    EBT = "EBT"
    TAX = "Tax"
    UNEXPLAINED = "Unexplained items"
    NET_INCOME = "Net income"

    CASH = "Cash"
    AR = "Accounts receivable"
    INVENTORY = "Inventory"
    PPE = "Net PP&E"
    OTHER_ASSETS = "Other assets"
    TOTAL_ASSETS = "Total assets"
    AP = "Accounts payable"
    DEBT = "Debt"
    OTHER_LIAB = "Other liabilities"
    EQUITY = "Book equity"
    TOTAL_LE = "Total liabilities and equity"

    INCREASE_AR = "Increase in receivables"
    INCREASE_INV = "Increase in inventory"
    INCREASE_AP = "Increase in payables"
    CFO_RESIDUAL = "CFO residual"
    CFO = "Cash from operations"
    CAPEX = "Capex"
    CFI_RESIDUAL = "CFI residual"
    CFI = "Cash from investing"
    DEBT_PAYDOWN = "Debt paydown"
    DEBT_DRAW = "Debt draw"
    DIVIDENDS = "Dividends"
    CFF_RESIDUAL = "CFF residual"
    CFF = "Cash from financing"
    NET_CHANGE = "Net change in cash"
    OPEN_CASH = "Opening cash"
    CLOSE_CASH = "Closing cash"
    ROLLFORWARD_GAP = "Rollforward gap"


INCOME_LINES = [
    Line.REVENUE,
    Line.COGS,
    Line.GROSS_PROFIT,
    Line.OPEX,
    Line.EBITDA,
    Line.DA,
    Line.EBIT,
    Line.INTEREST,
    Line.EBT,
    Line.TAX,
    Line.UNEXPLAINED,
    Line.NET_INCOME,
]

BALANCE_LINES = [
    Line.CASH,
    Line.AR,
    Line.INVENTORY,
    Line.PPE,
    Line.OTHER_ASSETS,
    Line.TOTAL_ASSETS,
    Line.AP,
    Line.DEBT,
    Line.OTHER_LIAB,
    Line.EQUITY,
    Line.TOTAL_LE,
]

CASHFLOW_LINES = [
    Line.NET_INCOME,
    Line.DA,
    Line.INCREASE_AR,
    Line.INCREASE_INV,
    Line.INCREASE_AP,
    Line.CFO_RESIDUAL,
    Line.CFO,
    Line.CAPEX,
    Line.CFI_RESIDUAL,
    Line.CFI,
    Line.DEBT_PAYDOWN,
    Line.DEBT_DRAW,
    Line.DIVIDENDS,
    Line.CFF_RESIDUAL,
    Line.CFF,
    Line.NET_CHANGE,
    Line.OPEN_CASH,
    Line.CLOSE_CASH,
    Line.ROLLFORWARD_GAP,
]

AUDIT_ROWS = [
    "balance_sheet_gap",
    "totals_gap",
    "income_statement_gap",
    "equity_rollforward_gap",
    "ppe_rollforward_gap",
    "debt_rollforward_gap",
    "receivables_gap",
    "inventory_gap",
    "payables_gap",
    "cfo_gap",
    "cfi_gap",
    "cff_gap",
    "net_change_gap",
    "opening_cash_gap",
    "closing_cash_gap",
    "cash_rollforward_gap",
]


@dataclass
class Stocks:
    cash: float
    ar: float
    inventory: float
    ppe: float
    other_assets: float
    ap: float
    debt: float
    other_liabilities: float
    equity: float

    def total_assets(self) -> float:
        return self.cash + self.ar + self.inventory + self.ppe + self.other_assets

    def total_le(self) -> float:
        return self.ap + self.debt + self.other_liabilities + self.equity


@dataclass
class OperatingDrivers:
    year: int
    revenue: float
    gross_margin: float
    opex_pct_sales: float
    da_pct_begin_ppe: float
    capex_pct_sales: float
    tax_rate: float
    dso: float
    dio: float
    dpo: float


@dataclass
class CorporatePolicy:
    interest_rate: float
    dividend_payout: float
    minimum_cash: float
    debt_paydown: float


@dataclass
class Operations:
    revenue: float
    cogs: float
    gross_profit: float
    opex: float
    ebitda: float
    da: float
    ebit: float
    capex: float
    end_ar: float
    end_inventory: float
    end_ap: float
    end_ppe: float
    increase_ar: float
    increase_inventory: float
    increase_ap: float


@dataclass
class Forecast:
    statements: Statements
    converged: bool
    iterations: int
    interest_mode: str


def frame(line_order: list[str], columns: dict[int, dict[str, float]]) -> pd.DataFrame:
    years = sorted(columns)
    data = {year: [float(columns[year][line]) for line in line_order] for year in years}
    out = pd.DataFrame(data, index=line_order)
    out.columns = [int(c) for c in out.columns]
    return out


def last_actual_year(statements: Statements) -> int:
    years = statements.income_years()
    if not years:
        raise ValueError("the case has no income statement")
    return years[-1]


def stocks_from_balance(column: pd.Series) -> Stocks:
    return Stocks(
        cash=float(column[Line.CASH]),
        ar=float(column[Line.AR]),
        inventory=float(column[Line.INVENTORY]),
        ppe=float(column[Line.PPE]),
        other_assets=float(column[Line.OTHER_ASSETS]),
        ap=float(column[Line.AP]),
        debt=float(column[Line.DEBT]),
        other_liabilities=float(column[Line.OTHER_LIAB]),
        equity=float(column[Line.EQUITY]),
    )


def balance_dict(stocks: Stocks) -> dict[str, float]:
    return {
        Line.CASH: stocks.cash,
        Line.AR: stocks.ar,
        Line.INVENTORY: stocks.inventory,
        Line.PPE: stocks.ppe,
        Line.OTHER_ASSETS: stocks.other_assets,
        Line.TOTAL_ASSETS: stocks.total_assets(),
        Line.AP: stocks.ap,
        Line.DEBT: stocks.debt,
        Line.OTHER_LIAB: stocks.other_liabilities,
        Line.EQUITY: stocks.equity,
        Line.TOTAL_LE: stocks.total_le(),
    }


def broadcast(value: float | list[float], n: int, name: str, *, extend: bool = False) -> list[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)] * n
    seq = [float(v) for v in value]
    if len(seq) == 1:
        return seq * n
    if len(seq) == n:
        return seq
    if extend and seq and len(seq) < n:
        return seq + [seq[-1]] * (n - len(seq))
    raise ValueError(f"{name} has {len(seq)} values; the forecast is {n} years")


def operate(stocks: Stocks, drivers: OperatingDrivers) -> Operations:
    revenue = drivers.revenue
    cogs = revenue * (1.0 - drivers.gross_margin)
    gross_profit = revenue - cogs
    opex = revenue * drivers.opex_pct_sales
    ebitda = gross_profit - opex
    da = drivers.da_pct_begin_ppe * stocks.ppe
    ebit = ebitda - da
    capex = drivers.capex_pct_sales * revenue
    end_ar = revenue * drivers.dso / DAYS
    end_inventory = cogs * drivers.dio / DAYS
    end_ap = cogs * drivers.dpo / DAYS
    return Operations(
        revenue=revenue,
        cogs=cogs,
        gross_profit=gross_profit,
        opex=opex,
        ebitda=ebitda,
        da=da,
        ebit=ebit,
        capex=capex,
        end_ar=end_ar,
        end_inventory=end_inventory,
        end_ap=end_ap,
        end_ppe=stocks.ppe + capex - da,
        increase_ar=end_ar - stocks.ar,
        increase_inventory=end_inventory - stocks.inventory,
        increase_ap=end_ap - stocks.ap,
    )


def _income_dict(op: Operations, interest: float, tax: float, unexplained: float, net_income: float) -> dict[str, float]:
    ebt = op.ebit - interest
    return {
        Line.REVENUE: op.revenue,
        Line.COGS: op.cogs,
        Line.GROSS_PROFIT: op.gross_profit,
        Line.OPEX: op.opex,
        Line.EBITDA: op.ebitda,
        Line.DA: op.da,
        Line.EBIT: op.ebit,
        Line.INTEREST: interest,
        Line.EBT: ebt,
        Line.TAX: tax,
        Line.UNEXPLAINED: unexplained,
        Line.NET_INCOME: net_income,
    }


def _cashflow_dict(
    *,
    net_income: float,
    da: float,
    increase_ar: float,
    increase_inventory: float,
    increase_ap: float,
    capex: float,
    paydown: float,
    draw: float,
    dividends: float,
    opening_cash: float,
    closing_cash: float,
    cfo_residual: float = 0.0,
    cfi_residual: float = 0.0,
    cff_residual: float = 0.0,
) -> dict[str, float]:
    cfo_computed = net_income + da - increase_ar - increase_inventory + increase_ap
    cfi_computed = -capex
    cff_computed = -paydown + draw - dividends
    cfo = cfo_computed + cfo_residual
    cfi = cfi_computed + cfi_residual
    cff = cff_computed + cff_residual
    net_change = cfo + cfi + cff
    gap = closing_cash - opening_cash - net_change
    return {
        Line.NET_INCOME: net_income,
        Line.DA: da,
        Line.INCREASE_AR: increase_ar,
        Line.INCREASE_INV: increase_inventory,
        Line.INCREASE_AP: increase_ap,
        Line.CFO_RESIDUAL: cfo_residual,
        Line.CFO: cfo,
        Line.CAPEX: capex,
        Line.CFI_RESIDUAL: cfi_residual,
        Line.CFI: cfi,
        Line.DEBT_PAYDOWN: paydown,
        Line.DEBT_DRAW: draw,
        Line.DIVIDENDS: dividends,
        Line.CFF_RESIDUAL: cff_residual,
        Line.CFF: cff,
        Line.NET_CHANGE: net_change,
        Line.OPEN_CASH: opening_cash,
        Line.CLOSE_CASH: closing_cash,
        Line.ROLLFORWARD_GAP: gap,
    }


def corporate_once(
    stocks: Stocks,
    drivers: OperatingDrivers,
    policy: CorporatePolicy,
    interest: float,
) -> tuple[Stocks, dict[str, float], dict[str, float], dict[str, float]]:
    op = operate(stocks, drivers)
    ebt = op.ebit - interest
    tax = drivers.tax_rate * ebt
    net_income = ebt - tax
    dividends = policy.dividend_payout * net_income if net_income > 0 else 0.0
    paydown = min(max(policy.debt_paydown, 0.0), max(stocks.debt, 0.0))
    cfo = net_income + op.da - op.increase_ar - op.increase_inventory + op.increase_ap
    cash_pre = stocks.cash + cfo - op.capex - paydown - dividends
    # The corporate revolver is uncapped. The LBO model caps its revolver.
    draw = max(0.0, policy.minimum_cash - cash_pre)
    end = Stocks(
        cash=cash_pre + draw,
        ar=op.end_ar,
        inventory=op.end_inventory,
        ppe=op.end_ppe,
        other_assets=stocks.other_assets,
        ap=op.end_ap,
        debt=stocks.debt - paydown + draw,
        other_liabilities=stocks.other_liabilities,
        equity=stocks.equity + net_income - dividends,
    )
    income = _income_dict(op, interest, tax, 0.0, net_income)
    cashflow = _cashflow_dict(
        net_income=net_income,
        da=op.da,
        increase_ar=op.increase_ar,
        increase_inventory=op.increase_inventory,
        increase_ap=op.increase_ap,
        capex=op.capex,
        paydown=paydown,
        draw=draw,
        dividends=dividends,
        opening_cash=stocks.cash,
        closing_cash=end.cash,
    )
    return end, income, balance_dict(end), cashflow


def corporate_year(
    stocks: Stocks,
    drivers: OperatingDrivers,
    policy: CorporatePolicy,
    interest: InterestMode,
) -> tuple[Stocks, dict[str, float], dict[str, float], dict[str, float], int, bool]:
    if interest == "beginning":
        guess = policy.interest_rate * stocks.debt
        end, income, balance, cashflow = corporate_once(stocks, drivers, policy, guess)
        return end, income, balance, cashflow, 1, True

    guess = policy.interest_rate * stocks.debt
    end, income, balance, cashflow = corporate_once(stocks, drivers, policy, guess)
    for iteration in range(1, 81):
        updated = policy.interest_rate * (stocks.debt + end.debt) / 2.0
        if abs(updated - guess) <= 1e-8:
            return end, income, balance, cashflow, iteration, True
        guess = updated
        end, income, balance, cashflow = corporate_once(stocks, drivers, policy, guess)
    return end, income, balance, cashflow, 80, False


def project(
    opening_year: int,
    opening: Stocks,
    years: list[tuple[OperatingDrivers, CorporatePolicy]],
    interest: InterestMode = "beginning",
) -> Forecast:
    if not years:
        raise ValueError("projection needs at least one year")
    prior = opening_year
    for drivers, _policy in years:
        if drivers.year <= prior:
            raise ValueError("forecast years must be strictly after the opening balance sheet")
        prior = drivers.year

    income: dict[int, dict[str, float]] = {}
    balance: dict[int, dict[str, float]] = {opening_year: balance_dict(opening)}
    cashflow: dict[int, dict[str, float]] = {}
    stocks = opening
    iterations = 1
    converged = True
    for drivers, policy in years:
        stocks, inc, bal, cf, steps, ok = corporate_year(stocks, drivers, policy, interest)
        income[drivers.year] = inc
        balance[drivers.year] = bal
        cashflow[drivers.year] = cf
        iterations = max(iterations, steps)
        converged = converged and ok

    return Forecast(
        statements=Statements(
            income=frame(INCOME_LINES, income),
            balance=frame(BALANCE_LINES, balance),
            cashflow=frame(CASHFLOW_LINES, cashflow),
        ),
        converged=converged,
        iterations=iterations,
        interest_mode=interest,
    )


def forecast_drivers(case: Case, n_years: int | None = None, *, extend: bool = False) -> list[OperatingDrivers]:
    n = case.assumptions.forecast_years if n_years is None else n_years
    assumptions = case.assumptions
    last_year = last_actual_year(case.history)
    revenue = float(case.history.income.loc[Line.REVENUE, last_year])
    if revenue <= 0:
        raise ValueError("latest revenue must be positive to forecast")
    growth = broadcast(assumptions.revenue_growth, n, "revenue_growth", extend=extend)
    gross_margin = broadcast(assumptions.gross_margin, n, "gross_margin", extend=extend)
    opex = broadcast(assumptions.opex_pct_sales, n, "opex_pct_sales", extend=extend)
    capex = broadcast(assumptions.capex_pct_sales, n, "capex_pct_sales", extend=extend)
    drivers: list[OperatingDrivers] = []
    for i in range(n):
        revenue = revenue * (1.0 + growth[i])
        drivers.append(
            OperatingDrivers(
                year=last_year + 1 + i,
                revenue=revenue,
                gross_margin=gross_margin[i],
                opex_pct_sales=opex[i],
                da_pct_begin_ppe=assumptions.da_pct_begin_ppe,
                capex_pct_sales=capex[i],
                tax_rate=assumptions.tax_rate,
                dso=assumptions.dso,
                dio=assumptions.dio,
                dpo=assumptions.dpo,
            )
        )
    return drivers


def forecast_statements(case: Case, interest: InterestMode = "beginning") -> Forecast:
    last_year = last_actual_year(case.history)
    if last_year not in case.history.balance_years():
        raise ValueError(f"no balance sheet for the latest income year {last_year}")
    opening = stocks_from_balance(case.history.balance[last_year])
    assumptions = case.assumptions
    paydown = broadcast(assumptions.debt_paydown, assumptions.forecast_years, "debt_paydown")
    paired = [
        (
            drivers,
            CorporatePolicy(
                interest_rate=assumptions.interest_rate,
                dividend_payout=assumptions.dividend_payout,
                minimum_cash=assumptions.minimum_cash,
                debt_paydown=paydown[i],
            ),
        )
        for i, drivers in enumerate(forecast_drivers(case))
    ]
    return project(last_year, opening, paired, interest=interest)


def combine(history: Statements, projected: Statements) -> Statements:
    def _cat(left: pd.DataFrame, right: pd.DataFrame) -> pd.DataFrame:
        # History wins on a duplicated opening year. Forecast flows are new columns.
        out = pd.concat([left, right], axis=1)
        out = out.loc[:, ~out.columns.duplicated(keep="first")]
        cols = sorted(int(c) for c in out.columns)
        out = out.reindex(columns=cols)
        out.columns = cols
        return out

    return Statements(
        income=_cat(history.income, projected.income),
        balance=_cat(history.balance, projected.balance),
        cashflow=_cat(history.cashflow, projected.cashflow),
    )


def _cell(df: pd.DataFrame, line: str, year: int) -> float:
    return float(df.loc[line, year])


def audit(statements: Statements) -> pd.DataFrame:
    """Gaps are in millions. Zero means the published lines satisfy that identity."""
    rows: dict[str, dict[int, float]] = {name: {} for name in AUDIT_ROWS}
    balance_years = statements.balance_years()

    for year in balance_years:
        assets = sum(_cell(statements.balance, line, year) for line in (
            Line.CASH, Line.AR, Line.INVENTORY, Line.PPE, Line.OTHER_ASSETS
        ))
        liabilities = sum(_cell(statements.balance, line, year) for line in (
            Line.AP, Line.DEBT, Line.OTHER_LIAB, Line.EQUITY
        ))
        rows["balance_sheet_gap"][year] = assets - liabilities
        rows["totals_gap"][year] = (
            _cell(statements.balance, Line.TOTAL_ASSETS, year)
            - _cell(statements.balance, Line.TOTAL_LE, year)
        )

    for year in statements.income_years():
        if year not in balance_years:
            continue
        position = balance_years.index(year)
        if position == 0:
            continue
        previous = balance_years[position - 1]
        income = statements.income
        flow = statements.cashflow
        begin = statements.balance

        mapped_ni = (
            _cell(income, Line.EBT, year)
            - _cell(income, Line.TAX, year)
            + _cell(income, Line.UNEXPLAINED, year)
        )
        rows["income_statement_gap"][year] = _cell(income, Line.NET_INCOME, year) - mapped_ni
        rows["equity_rollforward_gap"][year] = _cell(begin, Line.EQUITY, year) - (
            _cell(begin, Line.EQUITY, previous)
            + _cell(income, Line.NET_INCOME, year)
            - _cell(flow, Line.DIVIDENDS, year)
        )
        rows["ppe_rollforward_gap"][year] = _cell(begin, Line.PPE, year) - (
            _cell(begin, Line.PPE, previous)
            + _cell(flow, Line.CAPEX, year)
            - _cell(income, Line.DA, year)
        )
        rows["debt_rollforward_gap"][year] = _cell(begin, Line.DEBT, year) - (
            _cell(begin, Line.DEBT, previous)
            - _cell(flow, Line.DEBT_PAYDOWN, year)
            + _cell(flow, Line.DEBT_DRAW, year)
        )
        rows["receivables_gap"][year] = _cell(flow, Line.INCREASE_AR, year) - (
            _cell(begin, Line.AR, year) - _cell(begin, Line.AR, previous)
        )
        rows["inventory_gap"][year] = _cell(flow, Line.INCREASE_INV, year) - (
            _cell(begin, Line.INVENTORY, year) - _cell(begin, Line.INVENTORY, previous)
        )
        rows["payables_gap"][year] = _cell(flow, Line.INCREASE_AP, year) - (
            _cell(begin, Line.AP, year) - _cell(begin, Line.AP, previous)
        )
        cfo_computed = (
            _cell(income, Line.NET_INCOME, year)
            + _cell(income, Line.DA, year)
            - _cell(flow, Line.INCREASE_AR, year)
            - _cell(flow, Line.INCREASE_INV, year)
            + _cell(flow, Line.INCREASE_AP, year)
            + _cell(flow, Line.CFO_RESIDUAL, year)
        )
        rows["cfo_gap"][year] = _cell(flow, Line.CFO, year) - cfo_computed
        rows["cfi_gap"][year] = _cell(flow, Line.CFI, year) - (
            -_cell(flow, Line.CAPEX, year) + _cell(flow, Line.CFI_RESIDUAL, year)
        )
        rows["cff_gap"][year] = _cell(flow, Line.CFF, year) - (
            -_cell(flow, Line.DEBT_PAYDOWN, year)
            + _cell(flow, Line.DEBT_DRAW, year)
            - _cell(flow, Line.DIVIDENDS, year)
            + _cell(flow, Line.CFF_RESIDUAL, year)
        )
        rows["net_change_gap"][year] = _cell(flow, Line.NET_CHANGE, year) - (
            _cell(flow, Line.CFO, year)
            + _cell(flow, Line.CFI, year)
            + _cell(flow, Line.CFF, year)
        )
        rows["opening_cash_gap"][year] = (
            _cell(flow, Line.OPEN_CASH, year) - _cell(begin, Line.CASH, previous)
        )
        rows["closing_cash_gap"][year] = (
            _cell(flow, Line.CLOSE_CASH, year) - _cell(begin, Line.CASH, year)
        )
        rows["cash_rollforward_gap"][year] = _cell(flow, Line.ROLLFORWARD_GAP, year)

    return pd.DataFrame.from_dict(rows, orient="index").reindex(AUDIT_ROWS)


def max_abs_gap(gaps: pd.DataFrame) -> float:
    values = pd.to_numeric(gaps.stack(), errors="coerce").dropna().abs()
    if values.empty:
        return 0.0
    return float(values.max())


def identity_failures(gaps: pd.DataFrame, tol: float = TOL) -> pd.DataFrame:
    bad = gaps.abs() > tol
    if not bad.any().any():
        return gaps.iloc[0:0]
    return gaps.where(bad).dropna(how="all").dropna(axis=1, how="all")
