"""Trading comps on the latest fiscal year.

These are not next-twelve-months multiples. This model has no consensus
estimates. Outliers stay in the mean, the median, and the range.
The subject company is not a member of its own peer set.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from valuation.case import Case, Peer
from valuation.dcf import net_debt
from valuation.statements import Line, last_actual_year

BASIS_NOTE = (
    "Latest fiscal year, not a last-twelve-months stub and not a "
    "next-twelve-months estimate. The current price is paired with that year."
)


@dataclass
class CompsResult:
    subject: pd.DataFrame
    peers: pd.DataFrame
    stats: pd.DataFrame
    implied: pd.DataFrame
    basis_note: str
    warnings: list[str]


def _stats(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = {}
    for name in ("mean", "median", "min", "max"):
        rows[name] = {}
        for column in columns:
            series = pd.to_numeric(frame[column], errors="coerce").dropna()
            if series.empty:
                rows[name][column] = float("nan")
            elif name == "mean":
                rows[name][column] = float(series.mean())
            elif name == "median":
                rows[name][column] = float(series.median())
            elif name == "min":
                rows[name][column] = float(series.min())
            else:
                rows[name][column] = float(series.max())
    return pd.DataFrame.from_dict(rows, orient="index")


def _imply(multiple: float, metric: float, debt: float, shares: float, kind: str) -> tuple[float, float, float]:
    if kind == "ev":
        enterprise = multiple * metric
        equity = enterprise - debt
    else:
        enterprise = float("nan")
        equity = multiple * metric
    return enterprise, equity, equity / shares


def run_comps(case: Case, peers: list[Peer] | None = None) -> CompsResult:
    warnings: list[str] = []
    peer_list = case.peers if peers is None else peers
    if not peer_list:
        warnings.append("No peers. Pass peers=['MSFT', 'GOOGL'] when you load a live ticker.")
    if any(peer.synthetic for peer in peer_list) and not case.synthetic:
        warnings.append("Synthetic peer multiples were mixed with a live price. They were dropped.")
        peer_list = [peer for peer in peer_list if not peer.synthetic]
    year = last_actual_year(case.history)
    revenue = float(case.history.income.loc[Line.REVENUE, year])
    ebitda = float(case.history.income.loc[Line.EBITDA, year])
    earnings = float(case.history.income.loc[Line.NET_INCOME, year])
    debt = net_debt(case)
    price = case.price
    market_cap = price * case.shares if price is not None else float("nan")
    enterprise = market_cap + debt if price is not None else float("nan")

    def _ratio(numerator: float, denominator: float) -> float:
        if denominator == 0 or pd.isna(numerator) or pd.isna(denominator):
            return float("nan")
        return numerator / denominator

    subject = pd.DataFrame(
        [
            {
                "name": case.name,
                "year": year,
                "price": price if price is not None else float("nan"),
                "revenue": revenue,
                "ebitda": ebitda,
                "net_income": earnings,
                "net_debt": debt,
                "market_cap": market_cap,
                "enterprise_value": enterprise,
                "ev_sales": _ratio(enterprise, revenue),
                "ev_ebitda": _ratio(enterprise, ebitda),
                "pe": _ratio(market_cap, earnings),
            }
        ]
    )
    peer_rows = [
        {
            "name": peer.name,
            "ticker": peer.ticker or "",
            "synthetic": peer.synthetic,
            "ev_sales": peer.ev_sales,
            "ev_ebitda": peer.ev_ebitda,
            "pe": peer.pe,
        }
        for peer in peer_list
    ]
    peer_frame = pd.DataFrame(peer_rows, columns=["name", "ticker", "synthetic", "ev_sales", "ev_ebitda", "pe"])
    stats = _stats(peer_frame, ["ev_sales", "ev_ebitda", "pe"]) if not peer_frame.empty else pd.DataFrame()

    implied_rows = []
    specs = [
        ("EV/Sales", "ev_sales", revenue, "ev"),
        ("EV/EBITDA", "ev_ebitda", ebitda, "ev"),
        ("P/E", "pe", earnings, "equity"),
    ]
    for label, column, metric, kind in specs:
        if metric <= 0:
            warnings.append(f"{label} skipped: the subject's {column} metric is not positive.")
            continue
        if stats.empty or column not in stats.columns or pd.isna(stats.loc["median", column]):
            warnings.append(f"{label} skipped: no peer multiples.")
            continue
        row: dict[str, float | str] = {
            "method": label,
            "metric": metric,
            "multiple_low": float(stats.loc["min", column]),
            "multiple_median": float(stats.loc["median", column]),
            "multiple_high": float(stats.loc["max", column]),
        }
        for bound, key in (("multiple_low", "low"), ("multiple_median", "mid"), ("multiple_high", "high")):
            enterprise_value, equity_value, implied_price = _imply(
                float(row[bound]), metric, debt, case.shares, kind
            )
            row[f"enterprise_{key}"] = enterprise_value
            row[f"equity_{key}"] = equity_value
            row[f"price_{key}"] = implied_price
        implied_rows.append(row)
    implied = pd.DataFrame(implied_rows)
    return CompsResult(
        subject=subject,
        peers=peer_frame,
        stats=stats,
        implied=implied,
        basis_note=BASIS_NOTE,
        warnings=warnings,
    )
