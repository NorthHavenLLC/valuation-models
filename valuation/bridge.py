"""One case, several answers.

The bridge does not average the methods into a target price. The spread is the result.
"""

from __future__ import annotations

import math

import pandas as pd

from valuation.case import Case
from valuation.comps import run_comps
from valuation.dcf import run_dcf
from valuation.lbo import entry_equity_at_target_irr
from valuation.sotp import run_sotp


def _row(method: str, low: float, mid: float, high: float, shares: float, note: str) -> dict[str, float | str]:
    equity = mid * shares if isinstance(mid, (int, float)) and not math.isnan(mid) else float("nan")
    return {
        "method": method,
        "low": low,
        "mid": mid,
        "high": high,
        "equity_value": equity,
        "note": note,
    }


def _missing(method: str, note: str) -> dict[str, float | str]:
    return _row(method, float("nan"), float("nan"), float("nan"), 1.0, note) | {"equity_value": float("nan")}


def valuation_bridge(case: Case) -> pd.DataFrame:
    shares = case.shares
    rows: list[dict[str, float | str]] = []
    if case.price is not None:
        rows.append(_row("Market price", case.price, case.price, case.price, shares, case.timing_note))
    else:
        rows.append(_missing("Market price", "No price on the case."))

    try:
        dcf = run_dcf(case)
        rows.append(
            _row(
                "DCF, Gordon growth",
                dcf.gordon_price,
                dcf.gordon_price,
                dcf.gordon_price,
                shares,
                (
                    f"Terminal growth {case.assumptions.terminal_growth:.1%}. "
                    f"Terminal value is {dcf.gordon_tv_share:.0%} of enterprise value. "
                    f"WACC {dcf.wacc:.2%} ({dcf.weight_note})."
                ),
            )
        )
        rows.append(
            _row(
                "DCF, exit multiple",
                dcf.exit_price,
                dcf.exit_price,
                dcf.exit_price,
                shares,
                (
                    f"{case.assumptions.exit_ev_ebitda:.1f}x final-year EBITDA. "
                    f"Terminal value is {dcf.exit_tv_share:.0%} of enterprise value."
                ),
            )
        )
    except ValueError as exc:
        rows.append(_missing("DCF, Gordon growth", str(exc)))
        rows.append(_missing("DCF, exit multiple", str(exc)))

    comps = run_comps(case)
    if comps.implied.empty:
        rows.append(_missing("Comps", " ".join(comps.warnings) or "No comps."))
    else:
        for record in comps.implied.to_dict(orient="records"):
            rows.append(
                _row(
                    f"Comps {record['method']}",
                    float(record["price_low"]),
                    float(record["price_mid"]),
                    float(record["price_high"]),
                    shares,
                    "Peer min / median / max. Outliers are included. " + comps.basis_note,
                )
            )

    target = case.assumptions.lbo.target_irr
    try:
        bid = entry_equity_at_target_irr(case)
    except ValueError as exc:
        bid = None
        rows.append(_missing(f"LBO at {target:.0%} IRR", str(exc)))
    if bid is None and not any(str(row["method"]).startswith("LBO") for row in rows):
        rows.append(
            _missing(
                f"LBO at {target:.0%} IRR",
                "No purchase price hits the target IRR with this debt structure.",
            )
        )
    elif bid is not None:
        rows.append(
            _row(
                f"LBO at {target:.0%} IRR",
                bid / shares,
                bid / shares,
                bid / shares,
                shares,
                "Highest equity purchase price that still earns the target IRR. "
                "Debt is sized on EBITDA, so a higher price is funded with more sponsor equity.",
            )
        )

    if not case.segments:
        rows.append(_missing("Sum of the parts", "No segments on the case."))
    else:
        try:
            parts = run_sotp(case, basis="forward")
            rows.append(
                _row(
                    "Sum of the parts",
                    parts.price,
                    parts.price,
                    parts.price,
                    shares,
                    f"Forecast {parts.year} segment EBITDA, parent net debt once, "
                    f"conglomerate discount {case.assumptions.conglomerate_discount:.0%}.",
                )
            )
        except ValueError as exc:
            rows.append(_missing("Sum of the parts", str(exc)))

    return pd.DataFrame(rows)
