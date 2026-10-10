"""Shared notebook bootstrap: path, case load, firm-style banner."""

from __future__ import annotations

import sys
from pathlib import Path

from valuation.case import Case, Segment
from valuation.load import load_case
from valuation.report import case_banner


def project_root() -> Path:
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "valuation" / "__init__.py").exists():
            return candidate
    raise RuntimeError("Open this notebook from the project directory (or a subfolder of it).")


def ensure_path() -> Path:
    root = project_root()
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)
    return root


def open_case(
    ticker: str | None = None,
    peers: list[str] | None = None,
    segments: list[Segment] | None = None,
) -> Case:
    """Load the sample company or a live equity into the shared Case shape."""
    ensure_path()
    case = load_case(ticker, peers=peers, segments=segments)
    case_banner(case)
    return case


def show_case(case: Case) -> None:
    case_banner(case)


def boot(*, picker: bool = True):
    """One-cell notebook start: path, Plotly desk charts, active case (+ optional switcher).

    Returns ``(case, UNIT)``. Changing the compact picker updates ``cases/active.yaml``
    so every model notebook stays on the same equity (Micron by default).
    """
    ensure_path()
    from dataclasses import replace  # noqa: F401 — re-exported into notebooks via boot callers

    import matplotlib.pyplot as plt
    import pandas as pd  # noqa: F401

    from valuation import plots as viz
    from valuation.active import open_active_case, resolve_active

    viz.style()
    plt.rcParams["figure.dpi"] = 120

    if picker:
        from valuation.switcher import bind_compact_switcher

        case = bind_compact_switcher()
    else:
        case = open_active_case(show=True)

    try:
        from IPython import get_ipython

        ip = get_ipython()
        if ip is not None:
            ip.user_ns["case"] = case
            ip.user_ns["UNIT"] = case.unit
            ip.user_ns["ACTIVE"] = resolve_active()
            ip.user_ns["viz"] = viz
            ip.user_ns["plt"] = plt
            ip.user_ns["pd"] = pd
            ip.user_ns["replace"] = replace
    except Exception:
        pass

    return case, case.unit
