"""One switch for every notebook.

Edit ``cases/active.yaml`` (preset: micron, apple, sample, …), or call
``set_active_equity("MU")`` / the notebook dropdown. Every notebook calls
``open_active_case()`` and loads the same equity, peers, and segments.
Downloaded statements are cached under ``data/equities/`` so re-runs are fast.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from valuation.case import Case, Segment
from valuation.notebook import ensure_path, show_case
from valuation.load import load_case

CASES_DIR = Path(__file__).resolve().parents[1] / "cases"
ACTIVE_PATH = CASES_DIR / "active.yaml"
PRESETS_PATH = CASES_DIR / "presets.yaml"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Restore cases/active.yaml or cases/presets.yaml.")
    with path.open() as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a mapping")
    return data


def _write_active(active: dict[str, Any]) -> None:
    ACTIVE_PATH.write_text(
        "# Active case — edit preset, then re-run any notebook.\n"
        "# preset: sample | micron | apple | microsoft | nvidia | amd | custom\n\n"
        + yaml.safe_dump(active, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def list_presets() -> dict[str, dict[str, Any]]:
    presets = _read_yaml(PRESETS_PATH)
    return {str(k): v for k, v in presets.items() if isinstance(v, dict)}


def equity_choices() -> list[tuple[str, str]]:
    """Dropdown labels → preset keys (plus custom last)."""
    presets = list_presets()
    order = ["micron", "apple", "microsoft", "nvidia", "amd", "sample"]
    out: list[tuple[str, str]] = []
    for name in order:
        if name not in presets:
            continue
        spec = presets[name]
        ticker = spec.get("ticker")
        label = str(spec.get("label") or name)
        if ticker:
            out.append((f"{label}  ({ticker})", name))
        else:
            out.append((f"{label}  (synthetic)", name))
    for name, spec in sorted(presets.items()):
        if name in order:
            continue
        ticker = spec.get("ticker")
        label = str(spec.get("label") or name)
        out.append((f"{label}  ({ticker})" if ticker else label, name))
    out.append(("Custom ticker…", "custom"))
    return out


def resolve_active() -> dict[str, Any]:
    """Return {preset, label, ticker, peers, segments} for the active case."""
    active = _read_yaml(ACTIVE_PATH)
    name = str(active.get("preset") or "sample").strip().lower()
    presets = list_presets()

    if name == "custom":
        custom = active.get("custom") or {}
        ticker = custom.get("ticker")
        peers = list(custom.get("peers") or [])
        segments = _segments(custom.get("segments") or [])
        return {
            "preset": "custom",
            "label": f"Custom ({ticker})" if ticker else "Custom sample",
            "ticker": None if ticker in (None, "", "null") else str(ticker).strip().upper(),
            "peers": [str(p).strip().upper() for p in peers],
            "segments": segments,
        }

    if name not in presets:
        known = ", ".join(["sample", "custom", *sorted(p for p in presets if p != "sample")])
        raise ValueError(f"Unknown preset {name!r}. Choose one of: {known}")

    spec = presets[name]
    ticker = spec.get("ticker")
    return {
        "preset": name,
        "label": str(spec.get("label") or name),
        "ticker": None if ticker in (None, "", "null") else str(ticker).strip().upper(),
        "peers": [str(p).strip().upper() for p in (spec.get("peers") or [])],
        "segments": _segments(spec.get("segments") or []),
    }


def _segments(raw: list[Any]) -> list[Segment]:
    out: list[Segment] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(
            Segment(
                name=str(row["name"]),
                revenue_share=float(row["revenue_share"]),
                ebitda_margin=float(row["ebitda_margin"]),
                ev_ebitda=float(row["ev_ebitda"]),
            )
        )
    return out


def set_active_preset(preset: str) -> dict[str, Any]:
    """Rewrite cases/active.yaml to the named preset (keeps custom block)."""
    active = _read_yaml(ACTIVE_PATH)
    name = str(preset).strip().lower()
    if name != "custom" and name not in list_presets():
        raise ValueError(f"Unknown preset {name!r}")
    active["preset"] = name
    _write_active(active)
    return resolve_active()


def set_active_custom(
    ticker: str | None,
    peers: list[str] | None = None,
    segments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Point every notebook at an arbitrary ticker (preset becomes ``custom``)."""
    active = _read_yaml(ACTIVE_PATH)
    prev = active.get("custom") if isinstance(active.get("custom"), dict) else {}
    tick = None if ticker in (None, "", "null") else str(ticker).strip().upper()
    active["preset"] = "custom"
    active["custom"] = {
        "ticker": tick,
        "peers": [str(p).strip().upper() for p in (peers if peers is not None else prev.get("peers") or [])],
        "segments": segments if segments is not None else (prev.get("segments") or []),
    }
    _write_active(active)
    return resolve_active()


def set_active_equity(
    key: str,
    *,
    peers: list[str] | None = None,
) -> dict[str, Any]:
    """Switch by preset name, label, or ticker (e.g. ``micron``, ``MU``, ``Apple Inc.``)."""
    raw = str(key).strip()
    if not raw:
        raise ValueError("Pass a preset name or ticker.")
    lower = raw.lower()
    presets = list_presets()
    if lower in presets or lower == "custom":
        return set_active_preset(lower)

    upper = raw.upper()
    for name, spec in presets.items():
        ticker = spec.get("ticker")
        if ticker and str(ticker).strip().upper() == upper:
            return set_active_preset(name)
        label = str(spec.get("label") or "").strip().lower()
        if label and label == lower:
            return set_active_preset(name)

    return set_active_custom(upper, peers=peers)


def switch_case(key: str, *, show: bool = True, peers: list[str] | None = None) -> Case:
    """Set active equity and load it — one call for notebooks."""
    set_active_equity(key, peers=peers)
    return open_active_case(show=show)


def open_active_case(*, show: bool = True) -> Case:
    """Load whatever ``cases/active.yaml`` points at. Same case in every notebook."""
    ensure_path()
    spec = resolve_active()
    case = load_case(spec["ticker"], peers=spec["peers"] or None, segments=spec["segments"] or None)
    case.warnings.insert(
        0,
        f"Active: {spec['preset']} — {spec['label']}. "
        f"Use the equity picker in notebook 00, or set_active_equity(\"MU\").",
    )
    if spec["segments"] and not case.synthetic:
        case.warnings.append(
            "Segment table is an illustrative allocation from the preset, "
            "not an audited segment footnote."
        )
    if show:
        show_case(case)
    return case
