"""Download and cache equities for presets or the large modeling universe.

Usage:
  .venv/bin/python scripts/import_universe.py --universe --activate micron
  .venv/bin/python scripts/import_universe.py --preset micron
  .venv/bin/python scripts/import_universe.py --tickers MU AVGO AMD
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from valuation.active import list_presets, resolve_active, set_active_preset
from valuation.cache import list_cached
from valuation.load import _pull

UNIVERSE_PATH = ROOT / "cases" / "universe.yaml"


def _universe_tickers() -> list[str]:
    with UNIVERSE_PATH.open() as fh:
        data = yaml.safe_load(fh) or {}
    out: list[str] = []
    for key, rows in data.items():
        if key.startswith("#") or not isinstance(rows, list):
            continue
        for item in rows:
            if item:
                out.append(str(item).strip().upper())
    # Always fold in every preset ticker + peer so named cases are warm.
    for spec in list_presets().values():
        if spec.get("ticker"):
            out.append(str(spec["ticker"]).upper())
        out.extend(str(p).upper() for p in (spec.get("peers") or []))
    return out


def _dedupe(tickers: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tickers:
        if t and t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache equity statements into data/equities/")
    parser.add_argument("--preset", default=None, help="Preset name (default: active.yaml)")
    parser.add_argument("--tickers", nargs="*", default=None, help="Explicit ticker list")
    parser.add_argument("--universe", action="store_true", help="Import cases/universe.yaml (+ all presets)")
    parser.add_argument("--activate", default=None, nargs="?", const="micron",
                        help="Set cases/active.yaml after import (default micron if flag alone)")
    parser.add_argument("--refresh", action="store_true", help="Ignore cache age and re-download")
    args = parser.parse_args()

    tickers: list[str] = []
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    elif args.universe:
        tickers = _universe_tickers()
    else:
        name = args.preset or resolve_active()["preset"]
        presets = list_presets()
        if name == "custom":
            spec = resolve_active()
        elif name not in presets:
            raise SystemExit(f"Unknown preset {name}")
        else:
            spec = {
                "ticker": presets[name].get("ticker"),
                "peers": presets[name].get("peers") or [],
            }
        if spec.get("ticker"):
            tickers.append(str(spec["ticker"]).upper())
        tickers.extend(str(p).upper() for p in (spec.get("peers") or []))

    ordered = _dedupe(tickers)
    print(f"Importing {len(ordered)} tickers → data/equities/")
    ok, failed = [], []
    for symbol in ordered:
        try:
            _pull(symbol, refresh=args.refresh, max_age_hours=0 if args.refresh else 72)
            ok.append(symbol)
            print(f"  cached {symbol}")
        except Exception as exc:  # noqa: BLE001 — keep going through the universe
            failed.append((symbol, str(exc)))
            print(f"  FAIL {symbol}: {exc}")

    if args.activate:
        set_active_preset(args.activate)
        print(f"Active preset → {args.activate}")

    print(f"Done. Cached {len(list_cached())}: {', '.join(list_cached())}")
    if failed:
        print(f"Failed ({len(failed)}): {failed}")
        # Partial success is OK for a large universe import.
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
