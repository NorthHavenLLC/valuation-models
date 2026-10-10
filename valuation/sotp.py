"""Sum of the parts.

Each segment is a share of consolidated revenue times a margin times a
multiple. Corporate cost is valued once, as a drag. Parent net debt is
subtracted once. The latest balance sheet supplies that net debt even when
the segment earnings are next year's: forecast cash is not subtracted again.

A conglomerate discount is an assumption. It is applied to enterprise value
after the corporate drag and before net debt.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from valuation.case import Case
from valuation.dcf import net_debt
from valuation.statements import Line, forecast_statements, last_actual_year


@dataclass
class SotpResult:
    by_segment: pd.DataFrame
    enterprise_value: float
    enterprise_value_after_discount: float
    net_debt: float
    equity_value: float
    price: float
    consolidated_ebitda: float
    allocated_ebitda: float
    ebitda_gap: float
    basis: str
    year: int
    warnings: list[str]


def _empty(case: Case, basis: str, year: int, warning: str) -> SotpResult:
    return SotpResult(
        by_segment=pd.DataFrame(),
        enterprise_value=float("nan"),
        enterprise_value_after_discount=float("nan"),
        net_debt=net_debt(case),
        equity_value=float("nan"),
        price=float("nan"),
        consolidated_ebitda=float("nan"),
        allocated_ebitda=float("nan"),
        ebitda_gap=float("nan"),
        basis=basis,
        year=year,
        warnings=[warning],
    )


def run_sotp(case: Case, basis: str = "forward") -> SotpResult:
    if basis not in ("forward", "ltm"):
        raise ValueError("basis must be 'forward' or 'ltm'")
    if basis == "forward":
        forecast = forecast_statements(case)
        year = forecast.statements.income_years()[0]
        revenue = float(forecast.statements.income.loc[Line.REVENUE, year])
        ebitda = float(forecast.statements.income.loc[Line.EBITDA, year])
    else:
        year = last_actual_year(case.history)
        revenue = float(case.history.income.loc[Line.REVENUE, year])
        ebitda = float(case.history.income.loc[Line.EBITDA, year])

    if not case.segments:
        return _empty(
            case,
            basis,
            year,
            "No segments. Pass segments=[Segment(name, revenue_share, ebitda_margin, ev_ebitda)] to load_case.",
        )

    warnings: list[str] = []
    share_sum = sum(segment.revenue_share for segment in case.segments)
    if abs(share_sum - 1.0) > 0.02:
        warnings.append(f"Segment revenue shares sum to {share_sum:.1%}, not 100%.")

    rows = []
    allocated = 0.0
    enterprise = 0.0
    for segment in case.segments:
        seg_revenue = segment.revenue_share * revenue
        seg_ebitda = seg_revenue * segment.ebitda_margin
        seg_ev = seg_ebitda * segment.ev_ebitda
        allocated += seg_ebitda
        enterprise += seg_ev
        rows.append(
            {
                "segment": segment.name,
                "revenue": seg_revenue,
                "ebitda": seg_ebitda,
                "multiple": segment.ev_ebitda,
                "enterprise_value": seg_ev,
            }
        )

    drag = case.assumptions.corporate_drag_pct * revenue
    drag_ev = -drag * case.assumptions.corporate_multiple
    allocated -= drag
    enterprise += drag_ev
    rows.append(
        {
            "segment": "Corporate cost",
            "revenue": revenue,
            "ebitda": -drag,
            "multiple": case.assumptions.corporate_multiple,
            "enterprise_value": drag_ev,
        }
    )
    gap = allocated - ebitda
    tolerance = max(0.5, 0.02 * abs(ebitda))
    if abs(gap) > tolerance:
        warnings.append(
            f"Allocated EBITDA ({allocated:,.1f}) does not match consolidated EBITDA "
            f"({ebitda:,.1f}). The gap is {gap:,.1f}. Segment margins are an assumption."
        )
    discount = case.assumptions.conglomerate_discount
    after = enterprise * (1.0 - discount)
    rows.append(
        {
            "segment": "Conglomerate discount",
            "revenue": float("nan"),
            "ebitda": float("nan"),
            "multiple": discount,
            "enterprise_value": after - enterprise,
        }
    )
    debt = net_debt(case)
    equity = after - debt
    warnings.append(
        "Parent net debt is the latest balance sheet, subtracted once. "
        "Forecast cash is not subtracted again."
    )
    if basis == "forward":
        warnings.append("Segment earnings are forecast year 1. Net debt is still the latest balance sheet.")
    return SotpResult(
        by_segment=pd.DataFrame(rows),
        enterprise_value=enterprise,
        enterprise_value_after_discount=after,
        net_debt=debt,
        equity_value=equity,
        price=equity / case.shares,
        consolidated_ebitda=ebitda,
        allocated_ebitda=allocated,
        ebitda_gap=gap,
        basis=basis,
        year=year,
        warnings=warnings,
    )
