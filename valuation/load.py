"""Load the sample case, or map a live ticker into the same shape.

A live filing is not rewritten to make it balance. Cash stays the reported
cash. Anything the mapped lines do not cover sits in Other assets or Other
liabilities and is named as such. Working-capital days, margins, and growth
are mechanical readings of the latest year, held flat. They are not a forecast.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from valuation.case import Assumptions, Case, LboAssumptions, Peer, Segment
from valuation.sample import sample_case
from valuation.statements import (
    BALANCE_LINES,
    CASHFLOW_LINES,
    DAYS,
    INCOME_LINES,
    Line,
    Statements,
    _cashflow_dict,
    frame,
)

INCOME_ALIASES = {
    "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "EBIT"],
    "interest": ["Interest Expense", "Interest Expense Non Operating"],
    "tax": ["Tax Provision"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "pretax": ["Pretax Income"],
    "da": ["Reconciled Depreciation"],
}
BALANCE_ALIASES = {
    "cash": ["Cash And Cash Equivalents"],
    "cash_and_sti": ["Cash Cash Equivalents And Short Term Investments"],
    "ar": ["Accounts Receivable", "Receivables"],
    "inventory": ["Inventory"],
    "ppe": ["Net PPE"],
    "total_assets": ["Total Assets"],
    "ap": ["Accounts Payable", "Payables And Accrued Expenses", "Payables"],
    "current_debt": ["Current Debt", "Current Debt And Capital Lease Obligation"],
    "long_debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "total_debt": ["Total Debt"],
    "equity": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    "total_liab": ["Total Liabilities Net Minority Interest"],
}
CASHFLOW_ALIASES = {
    "cfo": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "cfi": ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities"],
    "cff": ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"],
    "capex": ["Capital Expenditure"],
    "da": ["Depreciation And Amortization", "Depreciation Amortization Depletion"],
    "dividends": ["Common Stock Dividend Paid", "Cash Dividends Paid"],
}


def load_case(
    ticker: str | None = None,
    peers: list[str] | None = None,
    segments: list[Segment] | None = None,
) -> Case:
    """Sample case when ticker is omitted. Otherwise the same models on that equity."""
    if ticker is None or str(ticker).strip() == "":
        case = sample_case()
        if peers:
            case.warnings.append(
                "Peers are ignored on the sample case. Its peer multiples are synthetic "
                "and are not mixed with live tickers."
            )
        if segments:
            case.segments = list(segments)
            case.warnings.append("Sample segments were replaced by the segments you passed.")
        return case
    return load_ticker(str(ticker).strip(), peers=peers, segments=segments)


def load_ticker(
    ticker: str,
    peers: list[str] | None = None,
    segments: list[Segment] | None = None,
) -> Case:
    income, balance, cashflow, price, shares, name, currency, beta = _pull(ticker)
    peer_rows: list[Peer] = []
    peer_warnings: list[str] = []
    if not peers:
        peer_warnings.append(
            "No peers supplied. Comps will not produce an implied price until you pass peers."
        )
    for symbol in peers or []:
        try:
            peer = _peer_from_ticker(symbol, expect_currency=currency)
        except ValueError as exc:
            peer_warnings.append(str(exc))
            continue
        if peer is None:
            peer_warnings.append(f"{symbol}: no usable peer multiple, left out of comps.")
            continue
        peer_rows.append(peer)
    case = map_reported(
        income,
        balance,
        cashflow,
        ticker=ticker,
        price=price,
        shares=shares,
        beta=beta,
        currency=currency,
        price_as_of=date.today().isoformat(),
        name=name,
        peers=peer_rows,
        segments=segments,
    )
    case.warnings.extend(peer_warnings)
    return case


def map_reported(
    income: pd.DataFrame,
    balance: pd.DataFrame,
    cashflow: pd.DataFrame | None,
    *,
    ticker: str,
    price: float | None,
    shares: float | None,
    beta: float | None,
    currency: str,
    price_as_of: str,
    name: str | None = None,
    peers: list[Peer] | None = None,
    segments: list[Segment] | None = None,
    quiet: bool = False,
) -> Case:
    if shares is None or shares <= 0:
        raise ValueError(f"Could not read shares outstanding for {ticker}.")
    warnings: list[str] = []
    inc = {key: _by_year(income, names) for key, names in INCOME_ALIASES.items()}
    bal = {key: _by_year(balance, names) for key, names in BALANCE_ALIASES.items()}
    flow = {key: _by_year(cashflow, names) for key, names in CASHFLOW_ALIASES.items()} if cashflow is not None else {}
    if not inc.get("revenue") or not inc.get("net_income"):
        raise ValueError(f"No revenue or net income line for {ticker}.")
    if not quiet:
        missing = [name for name in ("ar", "inventory", "ppe", "ap") if not bal.get(name)]
        if missing:
            warnings.append("Missing balance-sheet lines set to zero: " + ", ".join(missing) + ".")

    revenue_years = set((inc.get("revenue") or {}))
    balance_years = set((bal.get("cash") or {})) | set((bal.get("cash_and_sti") or {}))
    years = sorted(revenue_years & balance_years)
    if not years:
        raise ValueError(f"No overlapping income statement and balance sheet years for {ticker}.")

    def cash_at(year: int) -> float | None:
        if bal.get("cash") and year in bal["cash"]:
            return bal["cash"][year]
        if bal.get("cash_and_sti") and year in bal["cash_and_sti"]:
            return bal["cash_and_sti"][year]
        return None

    def debt_at(year: int) -> float:
        total = (bal.get("total_debt") or {}).get(year)
        if total is not None:
            return abs(total)
        current = (bal.get("current_debt") or {}).get(year, 0.0) or 0.0
        long_term = (bal.get("long_debt") or {}).get(year, 0.0) or 0.0
        if year not in (bal.get("current_debt") or {}) and year not in (bal.get("long_debt") or {}):
            return 0.0
        return abs(current) + abs(long_term)

    def equity_at(year: int) -> float | None:
        if bal.get("equity") and year in bal["equity"]:
            return bal["equity"][year]
        assets = (bal.get("total_assets") or {}).get(year)
        liabilities = (bal.get("total_liab") or {}).get(year)
        if assets is not None and liabilities is not None:
            if not quiet:
                warnings.append(f"{year}: book equity inferred as assets minus liabilities.")
            return assets - liabilities
        return None

    usable = [year for year in years if cash_at(year) is not None and equity_at(year) is not None]
    if not usable:
        raise ValueError(f"Could not map cash and equity for {ticker}.")
    if cash_at(usable[-1]) is None:
        raise ValueError(f"No cash line for {ticker}. Cash was not invented.")

    used_sti = bal.get("cash") is None and bal.get("cash_and_sti") is not None
    if used_sti and not quiet:
        warnings.append("Cash includes short-term investments. The source had no cash-only line.")
    if not quiet and (bal.get("total_debt") is None):
        warnings.append("Debt is current debt plus long-term debt. A total-debt line was not found.")
    if not quiet and not (bal.get("current_debt") or bal.get("long_debt") or bal.get("total_debt")):
        warnings.append("No debt line found. Debt is set to 0.")

    def da_at(year: int) -> float:
        if flow.get("da") and year in flow["da"]:
            return abs(flow["da"][year])
        if inc.get("da") and year in inc["da"]:
            return abs(inc["da"][year])
        return 0.0

    def optional(mapping: dict[int, float] | None, year: int, default: float = 0.0) -> float:
        if mapping is None or year not in mapping:
            return default
        return mapping[year]

    balance_cols: dict[int, dict[str, float]] = {}
    income_cols: dict[int, dict[str, float]] = {}
    cash_cols: dict[int, dict[str, float]] = {}
    flow_years = usable if len(usable) == 1 else usable[1:]
    if len(usable) == 1 and not quiet:
        warnings.append(
            f"Only one reported year ({usable[0]}). Working-capital changes are set to zero and are not a real cash flow."
        )

    plugs: list[tuple[int, float, float]] = []
    for year in usable:
        cash = float(cash_at(year))
        ar = optional(bal.get("ar"), year)
        inventory = optional(bal.get("inventory"), year)
        ppe = optional(bal.get("ppe"), year)
        ap = optional(bal.get("ap"), year)
        debt = debt_at(year)
        equity = float(equity_at(year))
        assets = (bal.get("total_assets") or {}).get(year)
        if assets is not None:
            other_assets = assets - cash - ar - inventory - ppe
            other_liab = assets - ap - debt - equity
        else:
            other_assets = 0.0
            other_liab = 0.0
        plugs.append((year, other_assets, other_liab))
        balance_cols[year] = {
            Line.CASH: cash,
            Line.AR: ar,
            Line.INVENTORY: inventory,
            Line.PPE: ppe,
            Line.OTHER_ASSETS: other_assets,
            Line.TOTAL_ASSETS: cash + ar + inventory + ppe + other_assets,
            Line.AP: ap,
            Line.DEBT: debt,
            Line.OTHER_LIAB: other_liab,
            Line.EQUITY: equity,
            Line.TOTAL_LE: ap + debt + other_liab + equity,
        }

    latest_plug_year, other_assets, other_liab = plugs[-1]
    if not quiet and (abs(other_assets) > 1 or abs(other_liab) > 1):
        warnings.append(
            f"Unclassified items in {latest_plug_year} sit in Other assets ({other_assets:,.1f}) and "
            f"Other liabilities ({other_liab:,.1f}). These are not cash."
        )

    reported_assets = (bal.get("total_assets") or {}).get(usable[-1])
    reported_liab = (bal.get("total_liab") or {}).get(usable[-1])
    reported_equity = (bal.get("equity") or {}).get(usable[-1])
    if (
        not quiet
        and reported_assets is not None
        and reported_liab is not None
        and reported_equity is not None
    ):
        reported_gap = reported_assets - reported_liab - reported_equity
        if abs(reported_gap) > 1:
            warnings.append(
                f"Reported assets minus liabilities minus equity is {reported_gap:,.1f}. "
                "The mapped sheet still uses a labeled residual so the lines foot. Cash was not adjusted."
            )

    for year in flow_years:
        previous = usable[usable.index(year) - 1] if len(usable) > 1 else None
        rev = inc["revenue"][year]
        gp = (inc.get("gross_profit") or {}).get(year)
        opinc = (inc.get("operating_income") or {}).get(year)
        if gp is None:
            gp = rev * 0.40
            if not quiet:
                warnings.append(f"{year}: gross profit was missing. Gross margin was set to 40% for the mapping.")
        cogs = rev - gp
        if opinc is None:
            opinc = gp
            if not quiet:
                warnings.append(f"{year}: operating income was missing.")
        da = da_at(year)
        ebit = opinc
        ebitda = ebit + da
        opex = gp - ebitda
        interest = abs(optional(inc.get("interest"), year))
        tax = optional(inc.get("tax"), year)
        net_income = inc["net_income"][year]
        ebt = ebit - interest
        unexplained = net_income - (ebt - tax)
        income_cols[year] = {
            Line.REVENUE: rev,
            Line.COGS: cogs,
            Line.GROSS_PROFIT: gp,
            Line.OPEX: opex,
            Line.EBITDA: ebitda,
            Line.DA: da,
            Line.EBIT: ebit,
            Line.INTEREST: interest,
            Line.EBT: ebt,
            Line.TAX: tax,
            Line.UNEXPLAINED: unexplained,
            Line.NET_INCOME: net_income,
        }

        if previous is None:
            incr_ar = incr_inv = incr_ap = 0.0
            open_cash = balance_cols[year][Line.CASH]
            begin_debt = balance_cols[year][Line.DEBT]
        else:
            incr_ar = balance_cols[year][Line.AR] - balance_cols[previous][Line.AR]
            incr_inv = balance_cols[year][Line.INVENTORY] - balance_cols[previous][Line.INVENTORY]
            incr_ap = balance_cols[year][Line.AP] - balance_cols[previous][Line.AP]
            open_cash = balance_cols[previous][Line.CASH]
            begin_debt = balance_cols[previous][Line.DEBT]
        end_debt = balance_cols[year][Line.DEBT]
        delta_debt = end_debt - begin_debt
        paydown, draw = (0.0, delta_debt) if delta_debt >= 0 else (-delta_debt, 0.0)
        capex = abs(optional(flow.get("capex"), year))
        dividends = abs(optional(flow.get("dividends"), year))
        cfo_computed = net_income + da - incr_ar - incr_inv + incr_ap
        cfi_computed = -capex
        cff_computed = -paydown + draw - dividends
        cfo_reported = (flow.get("cfo") or {}).get(year)
        cfi_reported = (flow.get("cfi") or {}).get(year)
        cff_reported = (flow.get("cff") or {}).get(year)
        cfo_residual = 0.0 if cfo_reported is None else cfo_reported - cfo_computed
        cfi_residual = 0.0 if cfi_reported is None else cfi_reported - cfi_computed
        cff_residual = 0.0 if cff_reported is None else cff_reported - cff_computed
        close_cash = balance_cols[year][Line.CASH]
        cash_cols[year] = _cashflow_dict(
            net_income=net_income,
            da=da,
            increase_ar=incr_ar,
            increase_inventory=incr_inv,
            increase_ap=incr_ap,
            capex=capex,
            paydown=paydown,
            draw=draw,
            dividends=dividends,
            opening_cash=open_cash,
            closing_cash=close_cash,
            cfo_residual=cfo_residual,
            cfi_residual=cfi_residual,
            cff_residual=cff_residual,
        )
        gap = cash_cols[year][Line.ROLLFORWARD_GAP]
        if not quiet and abs(gap) > 1:
            warnings.append(
                f"Cash rollforward gap in {year} is {gap:,.1f}. Cash was not adjusted."
            )

    history = Statements(
        income=frame(INCOME_LINES, income_cols),
        balance=frame(BALANCE_LINES, balance_cols),
        cashflow=frame(CASHFLOW_LINES, cash_cols),
    )
    assumptions = _assumptions_from_history(
        history, price=price, shares=shares / 1_000_000.0, beta=beta, warnings=warnings, quiet=quiet
    )
    fiscal_year = history.income_years()[-1]
    timing = (
        f"Price as of {price_as_of}. Statements are fiscal years through {fiscal_year}. "
        "Multiples use that fiscal year, not a true last-twelve-months stub and not a "
        "next-twelve-months estimate."
    )
    if not quiet:
        warnings.append(
            "Forecast drivers are the latest reported year, held flat. "
            "Risk-free rate 4%, equity risk premium 5%, terminal growth 2.5%, and "
            "the DCF exit multiple of 10x are assumptions, not a data feed. "
            "Edit case.assumptions before treating the output as an analysis."
        )
    return Case(
        name=name or ticker,
        ticker=ticker,
        currency=currency or "USD",
        unit=f"millions of {currency or 'USD'}",
        synthetic=False,
        source="yfinance",
        history=history,
        assumptions=assumptions,
        segments=list(segments or []),
        peers=list(peers or []),
        warnings=[] if quiet else warnings,
        timing_note=timing,
        fiscal_year=fiscal_year,
        price_as_of=price_as_of,
    )


def _assumptions_from_history(
    history: Statements,
    *,
    price: float | None,
    shares: float,
    beta: float | None,
    warnings: list[str],
    quiet: bool,
) -> Assumptions:
    year = history.income_years()[-1]
    income = history.income
    balance = history.balance
    cashflow = history.cashflow
    revenue = float(income.loc[Line.REVENUE, year])
    gross_profit = float(income.loc[Line.GROSS_PROFIT, year])
    opex = float(income.loc[Line.OPEX, year])
    da = float(income.loc[Line.DA, year])
    interest = float(income.loc[Line.INTEREST, year])
    tax = float(income.loc[Line.TAX, year])
    ebt = float(income.loc[Line.EBT, year])
    net_income = float(income.loc[Line.NET_INCOME, year])
    capex = float(cashflow.loc[Line.CAPEX, year])
    dividends = float(cashflow.loc[Line.DIVIDENDS, year])
    balance_years = history.balance_years()
    position = balance_years.index(year)
    previous = balance_years[position - 1] if position else None
    begin_ppe = float(balance.loc[Line.PPE, previous if previous is not None else year])
    begin_debt = float(balance.loc[Line.DEBT, previous if previous is not None else year])
    cogs = float(income.loc[Line.COGS, year])

    def _clip_rate(value: float, default: float, label: str, low: float, high: float) -> float:
        if low <= value <= high:
            return value
        if not quiet:
            warnings.append(f"{label} of {value:.1%} is outside a usable range. Using {default:.1%}.")
        return default

    if len(history.income_years()) >= 2:
        prior_year = history.income_years()[-2]
        prior_rev = float(income.loc[Line.REVENUE, prior_year])
        growth = revenue / prior_rev - 1.0 if prior_rev > 0 else 0.03
        growth = _clip_rate(growth, 0.03, "Latest revenue growth", -0.5, 0.5)
    else:
        growth = 0.03
        if not quiet:
            warnings.append("Revenue growth defaulted to 3% because there is only one income year.")

    gross_margin = gross_profit / revenue if revenue else 0.4
    opex_pct = opex / revenue if revenue else 0.2
    gross_margin = min(max(gross_margin, -0.5), 0.95)
    # Negative "opex" from filing map quirks — keep a usable operating cost share.
    if opex_pct < 0:
        if not quiet:
            warnings.append(
                f"Mapped OpEx/sales of {opex_pct:.1%} is negative; using 8% for the forecast."
            )
        opex_pct = 0.08
    opex_pct = min(opex_pct, 0.60)
    da_pct = da / begin_ppe if begin_ppe > 1 else 0.05
    da_pct = min(max(da_pct, 0.0), 0.5)
    capex_pct = capex / revenue if revenue else 0.05
    if ebt > 1:
        tax_rate = _clip_rate(tax / ebt, 0.25, "Effective tax rate", 0.0, 0.5)
    else:
        tax_rate = 0.25
        if not quiet:
            warnings.append("Tax rate defaulted to 25% because pretax income was not positive.")
    if begin_debt > 1:
        interest_rate = _clip_rate(interest / begin_debt, 0.06, "Interest rate", 0.0, 0.25)
    else:
        interest_rate = 0.06
        if not quiet:
            warnings.append("Interest rate defaulted to 6% because opening debt was missing or tiny.")
    payout = dividends / net_income if net_income > 1 else 0.0
    payout = min(max(payout, 0.0), 1.0)
    dso = float(balance.loc[Line.AR, year]) / revenue * DAYS if revenue else 45.0
    dio = float(balance.loc[Line.INVENTORY, year]) / cogs * DAYS if cogs > 1 else 0.0
    dpo = float(balance.loc[Line.AP, year]) / cogs * DAYS if cogs > 1 else 0.0

    ebitda = float(income.loc[Line.EBITDA, year])
    cash = float(balance.loc[Line.CASH, year])
    debt = float(balance.loc[Line.DEBT, year])
    if price is not None and ebitda > 0:
        entry_multiple = (price * shares + debt - cash) / ebitda
        if not quiet:
            warnings.append(
                f"LBO entry and exit multiples defaulted to the current fiscal-year EV/EBITDA "
                f"of {entry_multiple:.1f}x. That is the market's price, not a negotiated entry."
            )
    else:
        entry_multiple = 8.0
        if not quiet:
            warnings.append("LBO entry multiple defaulted to 8x.")
    used_beta = beta if beta is not None and beta > 0 else 1.0
    if beta is None and not quiet:
        warnings.append("Beta defaulted to 1.0.")

    minimum_cash = max(0.02 * revenue, 0.0)

    # Fade extreme cycle prints toward a usable forward path (still editable).
    if growth > 0.12:
        revenue_growth = [
            float(growth),
            float(0.55 * growth + 0.45 * 0.08),
            0.08,
            0.05,
            0.035,
        ]
        if not quiet:
            warnings.append(
                f"Revenue growth faded from {growth:.1%} toward mid-single digits across the forecast "
                f"(cycle print → steady state). Edit case.assumptions.revenue_growth to override."
            )
    else:
        revenue_growth = [float(growth)]

    maint_capex = min(max(da / revenue if revenue else 0.06, 0.04), 0.12)
    capex_obs = max(float(capex_pct), 0.0)
    if capex_obs > 0.14:
        capex_pct_sales = [
            capex_obs,
            0.6 * capex_obs + 0.4 * maint_capex,
            maint_capex + 0.02,
            maint_capex,
            maint_capex,
        ]
        if not quiet:
            warnings.append(
                f"Capex/sales faded from {capex_obs:.1%} toward maintenance ~{maint_capex:.1%} "
                f"so forecast UFCF is usable for DCF. Edit case.assumptions.capex_pct_sales to override."
            )
    else:
        capex_pct_sales = [capex_obs]

    # LBO defaults: use a modeling multiple when the spot EV/EBITDA is extreme.
    lbo_entry = float(entry_multiple)
    if lbo_entry > 18.0 or lbo_entry < 4.0:
        if not quiet:
            warnings.append(
                f"Spot EV/EBITDA {lbo_entry:.1f}x is outside a typical LBO entry band; "
                f"LBO model defaults to 10.0x entry/exit (editable)."
            )
        lbo_entry = 10.0

    return Assumptions(
        forecast_years=5,
        revenue_growth=revenue_growth,
        gross_margin=[gross_margin],
        opex_pct_sales=[opex_pct],
        da_pct_begin_ppe=da_pct,
        capex_pct_sales=capex_pct_sales,
        tax_rate=tax_rate,
        interest_rate=interest_rate,
        dso=max(dso, 0.0),
        dio=max(dio, 0.0),
        dpo=max(dpo, 0.0),
        dividend_payout=payout,
        minimum_cash=0.0,
        debt_paydown=[0.0],
        shares=shares,
        price=price,
        risk_free=0.04,
        equity_risk_premium=0.05,
        beta=used_beta,
        pretax_cost_of_debt=interest_rate,
        terminal_growth=0.025,
        exit_ev_ebitda=10.0,
        mid_year=False,
        target_debt_weight=None,
        corporate_drag_pct=0.0,
        corporate_multiple=8.0,
        conglomerate_discount=0.0,
        lbo=LboAssumptions(
            entry_ev_ebitda=lbo_entry,
            exit_ev_ebitda=lbo_entry,
            hold_years=5,
            target_irr=0.20,
            minimum_cash=minimum_cash,
            revolver_commitment=max(ebitda, 0.0),
            revolver_rate=interest_rate + 0.01,
            term_turns=3.0,
            term_rate=interest_rate + 0.02,
            term_amort_pct=0.05,
            notes_turns=1.5,
            notes_rate=interest_rate + 0.04,
            notes_amort_pct=0.0,
            cash_sweep=True,
            transaction_fee_pct=0.015,
            financing_fee_pct=0.02,
        ),
    )


def _pull(ticker: str, *, refresh: bool = False, max_age_hours: float | None = 24.0):
    """Pull statements. Prefer the local cache under data/equities/."""
    from valuation.cache import load_pull, save_pull

    symbol = ticker.strip().upper()
    if not refresh:
        cached = load_pull(symbol, max_age_hours=max_age_hours)
        if cached is not None:
            income, balance, cashflow, price, shares, name, currency, beta, _asof, _fetched = cached
            return income, balance, cashflow, price, shares, name, currency, beta

    # Stale or missing cache: allow an older cache if the network fails.
    stale = load_pull(symbol, max_age_hours=None) if not refresh else None
    try:
        import yfinance as yf
    except ImportError as exc:
        if stale is not None:
            income, balance, cashflow, price, shares, name, currency, beta, _asof, _fetched = stale
            return income, balance, cashflow, price, shares, name, currency, beta
        raise ValueError("yfinance is not installed.") from exc
    try:
        instrument = yf.Ticker(symbol)
        income = instrument.income_stmt
        balance = instrument.balance_sheet
        cashflow = instrument.cashflow
    except Exception as exc:
        if stale is not None:
            income, balance, cashflow, price, shares, name, currency, beta, _asof, _fetched = stale
            return income, balance, cashflow, price, shares, name, currency, beta
        raise ValueError(f"Could not download statements for {symbol}.") from exc
    if income is None or income.empty or balance is None or balance.empty:
        if stale is not None:
            income, balance, cashflow, price, shares, name, currency, beta, _asof, _fetched = stale
            return income, balance, cashflow, price, shares, name, currency, beta
        raise ValueError(f"No annual financial statements returned for {symbol}.")
    info: dict = {}
    try:
        info = instrument.info or {}
    except Exception:
        info = {}
    fast: dict = {}
    try:
        fast = dict(instrument.fast_info)
    except Exception:
        fast = {}
    price = _first(info, ["currentPrice", "regularMarketPrice", "previousClose"])
    if price is None:
        price = _num(fast.get("lastPrice", fast.get("last_price")))
    shares = _first(info, ["sharesOutstanding", "impliedSharesOutstanding"])
    if shares is None:
        shares = _num(fast.get("shares"))
    beta = _first(info, ["beta"])
    name = info.get("longName") or info.get("shortName") or symbol
    currency = info.get("currency") or "USD"
    save_pull(
        symbol,
        income=income,
        balance=balance,
        cashflow=cashflow,
        price=price,
        shares=shares,
        name=name,
        currency=currency,
        beta=beta,
    )
    return income, balance, cashflow, price, shares, name, currency, beta


def _peer_from_ticker(ticker: str, expect_currency: str | None = None) -> Peer | None:
    income, balance, cashflow, price, shares, name, currency, _beta = _pull(ticker)
    if price is None or shares is None:
        return None
    if expect_currency and currency and currency.upper() != expect_currency.upper():
        raise ValueError(
            f"{ticker}: statements currency {currency} ≠ subject {expect_currency}; "
            "left out so EV multiples are not mixed across FX."
        )
    mapped = map_reported(
        income,
        balance,
        cashflow,
        ticker=ticker,
        price=price,
        shares=shares,
        beta=None,
        currency=currency,
        price_as_of=date.today().isoformat(),
        name=name,
        quiet=True,
    )
    year = mapped.fiscal_year
    assert year is not None
    revenue = float(mapped.history.income.loc[Line.REVENUE, year])
    ebitda = float(mapped.history.income.loc[Line.EBITDA, year])
    earnings = float(mapped.history.income.loc[Line.NET_INCOME, year])
    debt = float(mapped.history.balance.loc[Line.DEBT, year]) - float(mapped.history.balance.loc[Line.CASH, year])
    market = price * mapped.shares
    enterprise = market + debt

    def ratio(numerator: float, denominator: float) -> float | None:
        if denominator <= 0:
            return None
        return numerator / denominator

    return Peer(
        name=name,
        ev_sales=ratio(enterprise, revenue),
        ev_ebitda=ratio(enterprise, ebitda),
        pe=ratio(market, earnings),
        synthetic=False,
        ticker=ticker,
    )


def _by_year(df: pd.DataFrame | None, names: list[str]) -> dict[int, float] | None:
    if df is None or df.empty:
        return None
    lookup = {str(label).strip().lower(): label for label in df.index}
    row = None
    for name in names:
        key = name.lower()
        if key in lookup:
            row = pd.to_numeric(df.loc[lookup[key]], errors="coerce")
            break
    if row is None:
        return None
    out: dict[int, float] = {}
    for column, value in row.items():
        if pd.isna(value):
            continue
        out[_year_of(column)] = float(value) / 1_000_000.0
    return out or None


def _year_of(column) -> int:
    if hasattr(column, "year"):
        return int(column.year)
    return int(str(column)[:4])


def _first(info: dict, keys: list[str]) -> float | None:
    for key in keys:
        value = _num(info.get(key))
        if value is not None:
            return value
    return None


def _num(value) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number
