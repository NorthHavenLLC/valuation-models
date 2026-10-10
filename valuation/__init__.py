"""Valuation models that share one case.

Each notebook imports this package and runs on its own. Pass a ticker to
load_case when you want the same equity through every model.
"""

from valuation.active import (
    equity_choices,
    list_presets,
    open_active_case,
    resolve_active,
    set_active_custom,
    set_active_equity,
    set_active_preset,
    switch_case,
)
from valuation.bridge import valuation_bridge
from valuation.case import Assumptions, Case, Peer, Segment
from valuation.comps import run_comps
from valuation.dcf import run_dcf
from valuation.lbo import entry_equity_at_target_irr, irr, run_lbo
from valuation.load import load_case
from valuation.notebook import boot, open_case
from valuation.sample import sample_case
from valuation.sotp import run_sotp
from valuation.statements import audit, combine, forecast_statements, identity_failures
from valuation.switcher import bind_compact_switcher, bind_equity_switcher

__all__ = [
    "Assumptions",
    "Case",
    "Peer",
    "Segment",
    "audit",
    "bind_compact_switcher",
    "bind_equity_switcher",
    "boot",
    "combine",
    "entry_equity_at_target_irr",
    "equity_choices",
    "forecast_statements",
    "identity_failures",
    "irr",
    "list_presets",
    "load_case",
    "open_active_case",
    "open_case",
    "resolve_active",
    "run_comps",
    "run_dcf",
    "run_lbo",
    "run_sotp",
    "sample_case",
    "set_active_custom",
    "set_active_equity",
    "set_active_preset",
    "switch_case",
    "valuation_bridge",
]
