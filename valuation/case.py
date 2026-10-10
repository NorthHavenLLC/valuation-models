"""Shared inputs for every model.

Figures are in millions of the case currency, except price (per share),
shares (millions of shares), rates, and multiples.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

# Identity failures smaller than this are float dust. 1e-4 million is $100.
TOL = 1e-4

Source = Literal["sample", "yfinance"]


@dataclass
class Segment:
    """Allocation rule for sum-of-the-parts, not a separate audited history."""

    name: str
    revenue_share: float
    ebitda_margin: float
    ev_ebitda: float

    def __post_init__(self) -> None:
        if not 0 <= self.revenue_share <= 1:
            raise ValueError(f"{self.name}: revenue share must be between 0 and 1")
        if self.ev_ebitda < 0:
            raise ValueError(f"{self.name}: EV/EBITDA multiple cannot be negative")


@dataclass
class Peer:
    name: str
    ev_sales: float | None
    ev_ebitda: float | None
    pe: float | None
    synthetic: bool
    ticker: str | None = None


@dataclass
class LboAssumptions:
    entry_ev_ebitda: float
    exit_ev_ebitda: float
    hold_years: int
    target_irr: float
    minimum_cash: float
    revolver_commitment: float
    revolver_rate: float
    term_turns: float
    term_rate: float
    term_amort_pct: float
    notes_turns: float
    notes_rate: float
    notes_amort_pct: float
    cash_sweep: bool
    transaction_fee_pct: float
    financing_fee_pct: float

    def __post_init__(self) -> None:
        if self.hold_years < 1:
            raise ValueError("LBO hold must be at least one year")
        if self.revolver_commitment < 0 or self.term_turns < 0 or self.notes_turns < 0:
            raise ValueError("LBO debt amounts cannot be negative")
        if not 0 < self.target_irr < 2:
            raise ValueError("target IRR must be between 0 and 200%")


@dataclass
class Assumptions:
    forecast_years: int
    revenue_growth: list[float]
    gross_margin: list[float]
    opex_pct_sales: list[float]
    da_pct_begin_ppe: float
    capex_pct_sales: list[float]
    tax_rate: float
    interest_rate: float
    dso: float
    dio: float
    dpo: float
    dividend_payout: float
    minimum_cash: float
    debt_paydown: list[float]
    shares: float
    price: float | None
    risk_free: float
    equity_risk_premium: float
    beta: float
    pretax_cost_of_debt: float
    terminal_growth: float
    exit_ev_ebitda: float
    mid_year: bool
    # None means "use book debt and the entered price". A number is a target weight.
    target_debt_weight: float | None
    corporate_drag_pct: float
    corporate_multiple: float
    conglomerate_discount: float
    lbo: LboAssumptions

    def __post_init__(self) -> None:
        if self.forecast_years < 1:
            raise ValueError("forecast_years must be positive")
        if self.shares <= 0:
            raise ValueError("shares must be positive")
        if not 0 <= self.tax_rate < 1:
            raise ValueError("tax rate must be in [0, 1)")
        if self.terminal_growth < 0:
            raise ValueError("terminal growth cannot be negative in this model")
        if not 0 <= self.conglomerate_discount < 1:
            raise ValueError("conglomerate discount must be in [0, 1)")
        if self.target_debt_weight is not None and not 0 <= self.target_debt_weight <= 1:
            raise ValueError("target debt weight must be between 0 and 1")
        if self.da_pct_begin_ppe < 0 or self.da_pct_begin_ppe >= 1:
            raise ValueError("D&A as a percent of opening PP&E must be in [0, 1)")
        if self.dso < 0 or self.dio < 0 or self.dpo < 0:
            raise ValueError("working-capital days cannot be negative")


@dataclass
class Statements:
    income: pd.DataFrame
    balance: pd.DataFrame
    cashflow: pd.DataFrame

    def income_years(self) -> list[int]:
        return [int(c) for c in self.income.columns]

    def balance_years(self) -> list[int]:
        return [int(c) for c in self.balance.columns]


@dataclass
class Case:
    name: str
    ticker: str | None
    currency: str
    unit: str
    synthetic: bool
    source: Source
    history: Statements
    assumptions: Assumptions
    segments: list[Segment]
    peers: list[Peer]
    warnings: list[str] = field(default_factory=list)
    timing_note: str = ""
    fiscal_year: int | None = None
    price_as_of: str | None = None

    @property
    def price(self) -> float | None:
        return self.assumptions.price

    @property
    def shares(self) -> float:
        return self.assumptions.shares
