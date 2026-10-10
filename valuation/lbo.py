"""Leveraged buyout.

Debt is sized on entry EBITDA, not on the price. Paying more is funded with
more sponsor equity. Fees are paid by the sponsor at close and do not reduce
company cash. Cash already in the business stays there; sellers are paid for
it through the equity purchase price, which is enterprise value minus old net debt.

The returns bridge explains the change in firm equity value:
EBITDA growth at the exit multiple, multiple change on entry EBITDA, and
deleveraging. Fees sit between that firm equity and the sponsor's check.
They are not a fourth operating source of value.

Exit equity is exit enterprise value minus ending net debt. It is not book equity.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from valuation.case import Case
from valuation.statements import (
    CASHFLOW_LINES,
    INCOME_LINES,
    Line,
    OperatingDrivers,
    Stocks,
    Statements,
    _cashflow_dict,
    _income_dict,
    audit,
    balance_dict,
    forecast_drivers,
    last_actual_year,
    max_abs_gap,
    operate,
    stocks_from_balance,
)
from valuation.case import TOL


def irr(cashflows: list[float]) -> float:
    """Annual IRR by bisection. Cash flows are t=0, t=1, ..."""
    if not any(cf > 0 for cf in cashflows) or not any(cf < 0 for cf in cashflows):
        raise ValueError("IRR needs both an outflow and an inflow")

    def npv(rate: float) -> float:
        return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))

    lo = -0.9
    hi = 1.0
    flo = npv(lo)
    bracketed = False
    for _ in range(40):
        fhi = npv(hi)
        if flo == 0:
            return lo
        if flo * fhi <= 0:
            bracketed = True
            break
        hi = hi * 2.0 + 0.1
    if not bracketed:
        raise ValueError("IRR is not bracketed between -90% and a very high rate")
    for _ in range(80):
        mid = (lo + hi) / 2.0
        fm = npv(mid)
        if abs(fm) < 1e-10 or abs(hi - lo) < 1e-12:
            return mid
        if flo * fm <= 0:
            hi = mid
        else:
            lo = mid
            flo = fm
    return (lo + hi) / 2.0


@dataclass
class LboResult:
    statements: Statements
    sources_uses: pd.DataFrame
    debt_schedule: pd.DataFrame
    returns_bridge: pd.DataFrame
    sponsor_cashflows: pd.DataFrame
    entry_ev: float
    entry_multiple: float
    entry_equity: float
    entry_ebitda: float
    firm_equity: float
    fees: float
    sponsor_equity: float
    exit_ev: float
    exit_ebitda: float
    exit_equity: float
    entry_net_debt: float
    exit_net_debt: float
    irr: float | None
    moic: float | None
    converged: bool
    warnings: list[str]


def _split(begin: float, end: float) -> tuple[float, float]:
    delta = end - begin
    if delta >= 0:
        return 0.0, delta
    return -delta, 0.0


def run_lbo(case: Case, entry_equity: float | None = None) -> LboResult:
    assumptions = case.assumptions
    lbo = assumptions.lbo
    warnings: list[str] = []
    last = last_actual_year(case.history)
    opening = stocks_from_balance(case.history.balance[last])
    entry_ebitda = float(case.history.income.loc[Line.EBITDA, last])
    if entry_ebitda <= 0:
        raise ValueError("LBO entry needs positive latest-year EBITDA")

    old_debt = opening.debt
    old_cash = opening.cash
    old_net_debt = old_debt - old_cash
    if entry_equity is None:
        entry_ev = lbo.entry_ev_ebitda * entry_ebitda
        purchase = entry_ev - old_net_debt
        entry_multiple = lbo.entry_ev_ebitda
    else:
        purchase = entry_equity
        entry_ev = purchase + old_net_debt
        entry_multiple = entry_ev / entry_ebitda

    term = lbo.term_turns * entry_ebitda
    notes = lbo.notes_turns * entry_ebitda
    if old_cash < lbo.minimum_cash:
        revolver_draw = min(lbo.minimum_cash - old_cash, lbo.revolver_commitment)
        if old_cash + revolver_draw + 1e-9 < lbo.minimum_cash:
            warnings.append("Revolver commitment cannot fund minimum cash at close.")
    else:
        revolver_draw = 0.0
    close_cash = old_cash + revolver_draw
    tx_fees = lbo.transaction_fee_pct * entry_ev
    fin_fees = lbo.financing_fee_pct * (term + notes + revolver_draw)
    fees = tx_fees + fin_fees
    cash_to_bs = revolver_draw
    # Fees are outside the company. The revolver draw is both a source and cash left on the sheet.
    sponsor = purchase + old_debt + fees + cash_to_bs - term - notes - revolver_draw
    uses = purchase + old_debt + tx_fees + fin_fees + cash_to_bs
    sources = term + notes + revolver_draw + sponsor

    if purchase < 0:
        warnings.append("Equity purchase price is negative: enterprise value is below old net debt.")
    if sponsor <= 0:
        warnings.append(
            "Sponsor equity is not positive. New debt covers the uses, so this is not a standard equity check."
        )

    close_debt = term + notes + revolver_draw
    close_assets_ex_equity = (
        close_cash + opening.ar + opening.inventory + opening.ppe + opening.other_assets
    )
    book_equity = close_assets_ex_equity - opening.ap - close_debt - opening.other_liabilities
    stocks = Stocks(
        cash=close_cash,
        ar=opening.ar,
        inventory=opening.inventory,
        ppe=opening.ppe,
        other_assets=opening.other_assets,
        ap=opening.ap,
        debt=close_debt,
        other_liabilities=opening.other_liabilities,
        equity=book_equity,
    )
    tranches = {"revolver": revolver_draw, "term": term, "notes": notes}
    original_term = term
    original_notes = notes

    drivers = forecast_drivers(case, lbo.hold_years, extend=True)
    if lbo.hold_years > assumptions.forecast_years:
        warnings.append(
            f"LBO hold is {lbo.hold_years} years and the forecast drivers were extended by repeating the last year."
        )

    income: dict[int, dict[str, float]] = {}
    balance: dict[int, dict[str, float]] = {last: balance_dict(stocks)}
    cashflow: dict[int, dict[str, float]] = {}
    schedule = [
        {
            "year": last,
            "phase": "close",
            "revolver": tranches["revolver"],
            "term": tranches["term"],
            "notes": tranches["notes"],
            "total_debt": close_debt,
            "cash": close_cash,
            "net_debt": close_debt - close_cash,
            "interest": 0.0,
            "mandatory": 0.0,
            "sweep": 0.0,
            "revolver_draw": revolver_draw,
            "ebitda": float("nan"),
            "net_income": float("nan"),
        }
    ]
    converged = True

    for driver in drivers:
        end_state, steps_ok, row = _lbo_year(
            stocks, tranches, driver, lbo, original_term, original_notes, warnings
        )
        stocks, tranches = end_state
        converged = converged and steps_ok
        income[driver.year] = row["income"]
        balance[driver.year] = row["balance"]
        cashflow[driver.year] = row["cashflow"]
        schedule.append(row["schedule"])

    if not converged:
        warnings.append("LBO interest did not converge within 80 iterations.")

    statements = Statements(
        income=pd.DataFrame({y: income[y] for y in income}).reindex(INCOME_LINES),
        balance=pd.DataFrame({y: balance[y] for y in balance}).reindex(
            list(balance_dict(stocks))
        ),
        cashflow=pd.DataFrame({y: cashflow[y] for y in cashflow}).reindex(CASHFLOW_LINES),
    )
    # Column order follows insertion, which is chronological. Force ints.
    for frame in (statements.income, statements.balance, statements.cashflow):
        frame.columns = [int(c) for c in frame.columns]

    gaps = max_abs_gap(audit(statements))
    if gaps > TOL:
        warnings.append(f"LBO statements failed an identity check by {gaps:.4f}.")

    exit_ebitda = float(statements.income.loc[Line.EBITDA, drivers[-1].year])
    exit_debt = float(statements.balance.loc[Line.DEBT, drivers[-1].year])
    exit_cash = float(statements.balance.loc[Line.CASH, drivers[-1].year])
    exit_net = exit_debt - exit_cash
    exit_ev = exit_ebitda * lbo.exit_ev_ebitda
    exit_equity = exit_ev - exit_net
    entry_net = close_debt - close_cash
    firm_equity = entry_ev - entry_net

    growth_value = (exit_ebitda - entry_ebitda) * lbo.exit_ev_ebitda
    multiple_value = entry_ebitda * (lbo.exit_ev_ebitda - entry_multiple)
    delever = entry_net - exit_net
    bridge = pd.DataFrame(
        [
            {"item": "Entry enterprise value", "amount": entry_ev},
            {"item": "Entry net debt, new structure", "amount": entry_net},
            {"item": "Entry firm equity", "amount": firm_equity},
            {"item": "Fees, outside the operating bridge", "amount": fees},
            {"item": "Sponsor equity invested", "amount": sponsor},
            {"item": "EBITDA growth at the exit multiple", "amount": growth_value},
            {"item": "Multiple change on entry EBITDA", "amount": multiple_value},
            {"item": "Deleveraging", "amount": delever},
            {"item": "Exit firm equity", "amount": exit_equity},
        ]
    )
    sources_uses = pd.DataFrame(
        [
            {"item": "Equity purchase price", "amount": purchase, "side": "use"},
            {"item": "Refinance existing debt", "amount": old_debt, "side": "use"},
            {"item": "Transaction fees", "amount": tx_fees, "side": "use"},
            {"item": "Financing fees", "amount": fin_fees, "side": "use"},
            {"item": "Cash to balance sheet", "amount": cash_to_bs, "side": "use"},
            {"item": "Total uses", "amount": uses, "side": "use"},
            {"item": "Term loan", "amount": term, "side": "source"},
            {"item": "Senior notes", "amount": notes, "side": "source"},
            {"item": "Revolver draw", "amount": revolver_draw, "side": "source"},
            {"item": "Sponsor equity", "amount": sponsor, "side": "source"},
            {"item": "Total sources", "amount": sources, "side": "source"},
        ]
    )

    irr_value: float | None
    moic: float | None
    if sponsor <= 0 or exit_equity <= 0:
        irr_value = None
        moic = None
        warnings.append("IRR is undefined when sponsor equity or exit equity is not positive.")
    else:
        flows = [-sponsor] + [0.0] * (lbo.hold_years - 1) + [exit_equity]
        irr_value = irr(flows)
        moic = exit_equity / sponsor
    cashflow_rows = [{"year": last, "sponsor_cash_flow": -sponsor}]
    for index, driver in enumerate(drivers):
        amount = exit_equity if index == len(drivers) - 1 else 0.0
        cashflow_rows.append({"year": driver.year, "sponsor_cash_flow": amount})

    return LboResult(
        statements=statements,
        sources_uses=sources_uses,
        debt_schedule=pd.DataFrame(schedule),
        returns_bridge=bridge,
        sponsor_cashflows=pd.DataFrame(cashflow_rows),
        entry_ev=entry_ev,
        entry_multiple=entry_multiple,
        entry_equity=purchase,
        entry_ebitda=entry_ebitda,
        firm_equity=firm_equity,
        fees=fees,
        sponsor_equity=sponsor,
        exit_ev=exit_ev,
        exit_ebitda=exit_ebitda,
        exit_equity=exit_equity,
        entry_net_debt=entry_net,
        exit_net_debt=exit_net,
        irr=irr_value,
        moic=moic,
        converged=converged,
        warnings=warnings,
    )


def _lbo_year(
    stocks: Stocks,
    tranches: dict[str, float],
    driver: OperatingDrivers,
    lbo,
    original_term: float,
    original_notes: float,
    warnings: list[str],
) -> tuple[tuple[Stocks, dict[str, float]], bool, dict]:
    begin_rev = tranches["revolver"]
    begin_term = tranches["term"]
    begin_notes = tranches["notes"]

    def once(interest: float):
        op = operate(stocks, driver)
        ebt = op.ebit - interest
        tax = driver.tax_rate * ebt
        net_income = ebt - tax
        cfo = net_income + op.da - op.increase_ar - op.increase_inventory + op.increase_ap
        cash_before = stocks.cash + cfo - op.capex
        mand_term = min(lbo.term_amort_pct * original_term, begin_term)
        mand_notes = min(lbo.notes_amort_pct * original_notes, begin_notes)
        mandatory = mand_term + mand_notes
        cash = cash_before - mandatory
        term_bal = begin_term - mand_term
        notes_bal = begin_notes - mand_notes
        rev_bal = begin_rev
        draw = 0.0
        if cash < lbo.minimum_cash:
            room = max(lbo.revolver_commitment - rev_bal, 0.0)
            draw = min(lbo.minimum_cash - cash, room)
            rev_bal += draw
            cash += draw
            sweep = 0.0
        else:
            sweep = 0.0
            if lbo.cash_sweep:
                excess = cash - lbo.minimum_cash
                pay_rev = min(excess, rev_bal)
                rev_bal -= pay_rev
                excess -= pay_rev
                pay_term = min(excess, term_bal)
                term_bal -= pay_term
                excess -= pay_term
                pay_notes = min(excess, notes_bal)
                notes_bal -= pay_notes
                excess -= pay_notes
                sweep = pay_rev + pay_term + pay_notes
                cash = lbo.minimum_cash + excess
        end_tranches = {"revolver": rev_bal, "term": term_bal, "notes": notes_bal}
        end_debt = rev_bal + term_bal + notes_bal
        begin_debt = begin_rev + begin_term + begin_notes
        paydown_rev, draw_rev = _split(begin_rev, rev_bal)
        paydown_term, draw_term = _split(begin_term, term_bal)
        paydown_notes, draw_notes = _split(begin_notes, notes_bal)
        paydown = paydown_rev + paydown_term + paydown_notes
        total_draw = draw_rev + draw_term + draw_notes
        end_equity = stocks.equity + net_income
        end_stocks = Stocks(
            cash=cash,
            ar=op.end_ar,
            inventory=op.end_inventory,
            ppe=op.end_ppe,
            other_assets=stocks.other_assets,
            ap=op.end_ap,
            debt=end_debt,
            other_liabilities=stocks.other_liabilities,
            equity=end_equity,
        )
        new_interest = (
            lbo.revolver_rate * (begin_rev + rev_bal) / 2.0
            + lbo.term_rate * (begin_term + term_bal) / 2.0
            + lbo.notes_rate * (begin_notes + notes_bal) / 2.0
        )
        payload = {
            "op": op,
            "interest": interest,
            "tax": tax,
            "net_income": net_income,
            "paydown": paydown,
            "draw": total_draw,
            "mandatory": mandatory,
            "sweep": sweep,
            "end_stocks": end_stocks,
            "end_tranches": end_tranches,
            "begin_debt": begin_debt,
            "end_debt": end_debt,
            "shortfall": max(0.0, lbo.minimum_cash - cash),
        }
        return new_interest, payload

    guess = (
        lbo.revolver_rate * begin_rev
        + lbo.term_rate * begin_term
        + lbo.notes_rate * begin_notes
    )
    updated, payload = once(guess)
    ok = False
    for _ in range(80):
        if abs(updated - guess) <= 1e-8:
            ok = True
            break
        guess = updated
        updated, payload = once(guess)
    else:
        guess = updated
        _, payload = once(guess)

    # Rebuild the published interest from the converged balances, then accept `updated`.
    if not ok:
        payload["interest"] = guess
    else:
        payload["interest"] = updated
    op = payload["op"]
    # The last once() call used `guess` as the interest in the income statement,
    # while `updated` is the interest implied by the resulting balances.
    # One extra evaluation locks the income statement to that interest.
    _, payload = once(updated if ok else guess)
    if payload["shortfall"] > 1e-6:
        warnings.append(f"{driver.year}: revolver commitment could not fund minimum cash.")
    op = payload["op"]
    end_stocks = payload["end_stocks"]
    income = _income_dict(op, payload["interest"], payload["tax"], 0.0, payload["net_income"])
    cashflow = _cashflow_dict(
        net_income=payload["net_income"],
        da=op.da,
        increase_ar=op.increase_ar,
        increase_inventory=op.increase_inventory,
        increase_ap=op.increase_ap,
        capex=op.capex,
        paydown=payload["paydown"],
        draw=payload["draw"],
        dividends=0.0,
        opening_cash=stocks.cash,
        closing_cash=end_stocks.cash,
    )
    row = {
        "income": income,
        "balance": balance_dict(end_stocks),
        "cashflow": cashflow,
        "schedule": {
            "year": driver.year,
            "phase": "hold",
            "revolver": payload["end_tranches"]["revolver"],
            "term": payload["end_tranches"]["term"],
            "notes": payload["end_tranches"]["notes"],
            "total_debt": payload["end_debt"],
            "cash": end_stocks.cash,
            "net_debt": payload["end_debt"] - end_stocks.cash,
            "interest": payload["interest"],
            "mandatory": payload["mandatory"],
            "sweep": payload["sweep"],
            "revolver_draw": payload["draw"],
            "ebitda": op.ebitda,
            "net_income": payload["net_income"],
        },
    }
    return (end_stocks, payload["end_tranches"]), ok, row


def entry_equity_at_target_irr(case: Case) -> float | None:
    """Equity purchase price at which the sponsor IRR equals the target.

    This is a bid for the shares, not the sponsor's equity check.
    A price near zero can make sponsor equity negative, because the debt
    covers the uses. The search starts at the cheapest price that still
    requires a sponsor check.
    """
    target = case.assumptions.lbo.target_irr

    def priced(equity: float) -> LboResult:
        return run_lbo(case, entry_equity=equity)

    def has_irr(result: LboResult) -> bool:
        return result.sponsor_equity > 0 and result.irr is not None

    lo = 0.0
    hi = max(case.shares * (case.price or 1.0) * 0.05, 1.0)
    probe = priced(hi)
    for _ in range(30):
        if has_irr(probe):
            break
        lo = hi
        hi *= 2.0
        probe = priced(hi)
    else:
        return None

    for _ in range(40):
        mid = (lo + hi) / 2.0
        mid_result = priced(mid)
        if has_irr(mid_result):
            hi = mid
            probe = mid_result
        else:
            lo = mid

    if probe.irr is None or probe.irr < target:
        return None

    lo = hi
    for _ in range(24):
        current = priced(hi)
        if not has_irr(current) or current.irr <= target:
            break
        lo = hi
        hi *= 1.8
    else:
        return None

    for _ in range(60):
        mid = (lo + hi) / 2.0
        current = priced(mid)
        if has_irr(current) and current.irr > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0
