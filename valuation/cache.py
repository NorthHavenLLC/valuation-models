"""Local cache of Yahoo Finance annual statements.

Cached under data/equities/{TICKER}.pkl so presets like Micron travel with the
project and notebooks do not re-download on every Run All.
"""

from __future__ import annotations

import pickle
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "equities"
DEFAULT_MAX_AGE_HOURS = 24


def cache_path(ticker: str) -> Path:
    return DATA_DIR / f"{ticker.strip().upper()}.pkl"


def list_cached() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(p.stem for p in DATA_DIR.glob("*.pkl"))


def save_pull(
    ticker: str,
    *,
    income: pd.DataFrame,
    balance: pd.DataFrame,
    cashflow: pd.DataFrame | None,
    price: float | None,
    shares: float | None,
    name: str,
    currency: str,
    beta: float | None,
) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(ticker)
    payload = {
        "ticker": ticker.strip().upper(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "price_as_of": date.today().isoformat(),
        "income": income,
        "balance": balance,
        "cashflow": cashflow,
        "price": price,
        "shares": shares,
        "name": name,
        "currency": currency,
        "beta": beta,
    }
    with path.open("wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_pull(ticker: str, *, max_age_hours: float | None = DEFAULT_MAX_AGE_HOURS):
    path = cache_path(ticker)
    if not path.exists():
        return None
    with path.open("rb") as fh:
        payload = pickle.load(fh)
    if max_age_hours is not None:
        fetched = datetime.fromisoformat(payload["fetched_at"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - fetched).total_seconds() / 3600.0
        if age_h > max_age_hours:
            return None
    return (
        payload["income"],
        payload["balance"],
        payload["cashflow"],
        payload["price"],
        payload["shares"],
        payload["name"],
        payload["currency"],
        payload["beta"],
        payload.get("price_as_of", date.today().isoformat()),
        payload.get("fetched_at"),
    )
