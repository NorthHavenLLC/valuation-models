"""Research-figure charting for the valuation notebooks.

SSRN / arXiv print aesthetic via ``valuation.theme``. Interactive Plotly by
default (orbitable 3D, hoverable heatmaps). Set VALUATION_CHARTS=matplotlib
to force the matplotlib path.
"""

from __future__ import annotations

from dataclasses import replace
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import colors
from matplotlib.colors import LightSource, TwoSlopeNorm
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

from valuation import theme as T
from valuation.case import Case
from valuation.dcf import (
    discount_factor,
    gordon_terminal_value,
    net_debt,
    present_value,
    run_dcf,
    unlevered_fcf,
)
from valuation.lbo import run_lbo
from valuation.statements import Line, forecast_statements

CHART_ENGINE = os.environ.get("VALUATION_CHARTS", "plotly").strip().lower()


def _use_plotly() -> bool:
    if CHART_ENGINE in {"mpl", "matplotlib"}:
        return False
    try:
        import plotly  # noqa: F401

        return True
    except ImportError:
        return False


PALETTE = T.PALETTE
SERIES = T.SERIES
_cmaps = T.mpl_cmaps()
CMAP_SURFACE = _cmaps["surface"]
CMAP_SEQ = _cmaps["seq"]
CMAP_DIV = _cmaps["div"]


def style() -> None:
    """Apply research-paper rcParams (matplotlib fallback path)."""
    plt.rcParams.update(
        {
            "figure.figsize": (11.0, 5.6),
            "figure.dpi": 150,
            "figure.facecolor": T.PAPER,
            "axes.facecolor": T.PLOT,
            "axes.edgecolor": T.RULE,
            "axes.labelcolor": T.MUTE,
            "axes.titlecolor": T.INK,
            "axes.titleweight": "semibold",
            "axes.titlesize": 14,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.spines.bottom": True,
            "axes.linewidth": 0.7,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": T.GRID,
            "grid.alpha": 0.95,
            "grid.linewidth": 0.55,
            "xtick.color": T.MUTE,
            "ytick.color": T.MUTE,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "font.size": 9.5,
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
            "legend.frameon": False,
            "legend.fontsize": 9,
            "lines.linewidth": 2.2,
            "savefig.facecolor": T.PAPER,
            "savefig.bbox": "tight",
        }
    )


def desk_axes(ax, *, y_right: bool = True) -> None:
    """Cboe-style axes: horizontal grid only, Y ticks on the right."""
    ax.set_facecolor(PALETTE["paper"])
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(not y_right)
    ax.spines["right"].set_visible(y_right)
    ax.spines["bottom"].set_visible(True)
    for spine in ax.spines.values():
        spine.set_color(PALETTE["grid"])
        spine.set_linewidth(0.7)
    ax.grid(True, axis="y", color=PALETTE["grid"], linewidth=0.6, alpha=0.95)
    ax.grid(False, axis="x")
    ax.tick_params(axis="both", colors=PALETTE["mute"], length=3, width=0.6)
    if y_right:
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
    else:
        ax.yaxis.tick_left()
        ax.yaxis.set_label_position("left")
    ax.set_axisbelow(True)


def _finish(fig: plt.Figure, title: str | None = None, caption: str | None = None) -> plt.Figure:
    """Light chrome pass: horizontal grid preference; leave bar/heatmap Y placement alone."""
    seen_positions = set()
    for ax in fig.axes:
        if getattr(ax, "name", None) == "3d":
            continue
        if hasattr(ax, "get_subplotspec") and ax.get_subplotspec() is None:
            continue
        ax.set_facecolor(PALETTE["paper"])
        ax.spines["top"].set_visible(False)
        position = tuple(ax.get_position().bounds)
        ax.grid(False, axis="x")
        if position in seen_positions:
            ax.grid(False)
        else:
            ax.grid(True, axis="y", color=PALETTE["grid"], linewidth=0.6, alpha=0.95)
        seen_positions.add(position)
        ax.set_axisbelow(True)
    if title:
        fig.suptitle(title, fontsize=12.5, fontweight="semibold", color=PALETTE["ink"], y=0.98)
    if caption:
        fig.text(0.5, 0.01, caption, ha="center", va="bottom", fontsize=8, color=PALETTE["mute"], style="italic")
    fig.subplots_adjust(left=0.07, right=0.97, top=0.9 if title else 0.95, bottom=0.1 if caption else 0.08)
    return fig


def plot_desk_series(
    frame: pd.DataFrame,
    *,
    title: str | None = None,
    ylabel: str = "",
    y_as_pct: bool = False,
    colors: list[str] | None = None,
    watermark: str | None = None,
):
    """Multi-series line chart matching the desk UI reference.

    ``frame`` columns are series; the index is the x-axis (years or dates).
    Uses Plotly by default for interactive hover / zoom.
    """
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_desk_series(frame, title=title, ylabel=ylabel, y_as_pct=y_as_pct, colors=colors)

    data = frame.astype(float).copy()
    if y_as_pct:
        data = data * 100.0
    fig, ax = plt.subplots(figsize=(11.2, 5.2))
    palette = colors or [T.FINANCIAL.get(str(col), SERIES[i % len(SERIES)])
                         for i, col in enumerate(data.columns)]
    for i, col in enumerate(data.columns):
        ax.plot(
            data.index,
            data[col],
            color=palette[i % len(palette)],
            lw=1.55,
            solid_capstyle="round",
            label=str(col),
        )
    handles = [
        Line2D([0], [0], color=palette[i % len(palette)], lw=2.2, label=str(col))
        for i, col in enumerate(data.columns)
    ]
    direct = not data.empty and 1 <= len(data.columns) <= 5 and np.isfinite(data.iloc[-1]).all()
    if not direct:
        ax.legend(handles=handles, loc="upper left", fontsize=8.5, handlelength=1.6)
    if ylabel:
        ax.set_ylabel(ylabel if not y_as_pct else f"{ylabel} (%)".replace(" (%) (%)", " (%)"))
    if y_as_pct:
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g} %"))
    if watermark:
        ax.text(
            0.98, 0.92, watermark, transform=ax.transAxes,
            ha="right", va="top", fontsize=28, color=PALETTE["fog"],
            fontweight="bold", alpha=0.85, zorder=0,
        )
    desk_axes(ax, y_right=not direct)
    if title:
        ax.set_title(title, loc="left", fontsize=11, fontweight="semibold", color=PALETTE["ink"], pad=10)
    fig.subplots_adjust(left=0.04, right=0.92, top=0.9, bottom=0.1)
    if direct:
        fig.subplots_adjust(left=.08, right=.77)
        values = data.iloc[-1].to_numpy(dtype=float)
        lo, hi = ax.get_ylim()
        points = (values-lo)/(hi-lo)*fig.get_figheight()*72*.8
        adjusted = points.copy()
        order = np.argsort(points)
        for previous, current in zip(order, order[1:]):
            adjusted[current] = max(adjusted[current], adjusted[previous]+16)
        adjusted -= float(np.mean(adjusted-points))
        for i, (col, value) in enumerate(zip(data.columns, values)):
            ax.annotate(f"{col} · {value:,.1f}" + ("%" if y_as_pct else ""),
                        xy=(1, value), xycoords=("axes fraction", "data"),
                        xytext=(10, float(adjusted[i]-points[i])), textcoords="offset points",
                        fontsize=9, color=palette[i % len(palette)], va="center")
    return fig


def _contrast_text(value: float, vmin: float, vmax: float) -> str:
    mid = (vmin + vmax) / 2.0
    return "white" if value >= mid else PALETTE["ink"]


def _shade_forecast(ax, years: list[int], split_year: int | None) -> None:
    if split_year is None or not years:
        return
    future = [y for y in years if y > split_year]
    if not future:
        return
    ax.axvspan(min(future) - 0.5, max(future) + 0.5, color=PALETTE["soft"], zorder=0)


def show_df(frame: pd.DataFrame | pd.Series, digits: int = 1):
    from valuation.report import table

    if isinstance(frame, pd.Series):
        table(frame.to_frame(), digits=digits)
    else:
        table(frame, digits=digits)


# ---------------------------------------------------------------------------
# Three-statement
# ---------------------------------------------------------------------------


def plot_income_stack(statements, unit: str = "", history_end: int | None = None):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_income_stack(statements, unit, history_end=history_end)
    years = [int(c) for c in statements.income.columns]
    revenue = statements.income.loc[Line.REVENUE].astype(float)
    cogs = statements.income.loc[Line.COGS].astype(float)
    opex = statements.income.loc[Line.OPEX].astype(float)
    da = statements.income.loc[Line.DA].astype(float)
    ebit = statements.income.loc[Line.EBIT].astype(float)
    ebitda = statements.income.loc[Line.EBITDA].astype(float)
    ni = statements.income.loc[Line.NET_INCOME].astype(float)

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.1))
    _shade_forecast(axes[0], years, history_end)
    _shade_forecast(axes[1], years, history_end)

    axes[0].stackplot(
        years, cogs, opex, da, ebit,
        labels=["COGS", "OpEx", "D&A", "EBIT"],
        colors=[T.FINANCIAL[n] for n in ("COGS", "OpEx", "D&A", "EBIT")],
        alpha=0.88,
    )
    axes[0].plot(years, revenue, color=PALETTE["ink"], marker="o", ms=4.5, lw=1.8, label="Revenue")
    axes[0].set_title("Revenue composition")
    axes[0].set_ylabel(unit)
    axes[0].legend(loc="upper left", fontsize=7.5, ncol=2)

    for series, color, label in (
        (ebit, T.FINANCIAL["EBIT"], "EBIT"),
        (ebitda, T.FINANCIAL["EBITDA"], "EBITDA"),
        (ni, T.FINANCIAL["Net income"], "Net income"),
    ):
        axes[1].plot(years, series, color=color, lw=1.55, label=label)
    desk_axes(axes[1], y_right=False)
    axes[1].set_title("Earnings")
    axes[1].set_ylabel(unit)
    lines, labels = axes[1].get_legend_handles_labels()
    axes[1].legend(lines, labels, loc="upper left", fontsize=7.5)
    return _finish(fig, caption="Shaded years are forecasts." if history_end is not None else None)


def plot_balance_composition(statements, unit: str = "", history_end: int | None = None):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_balance_composition(statements, unit, history_end=history_end)
    years = [int(c) for c in statements.balance.columns]
    assets = [
        statements.balance.loc[Line.CASH].astype(float),
        statements.balance.loc[Line.AR].astype(float),
        statements.balance.loc[Line.INVENTORY].astype(float),
        statements.balance.loc[Line.PPE].astype(float),
        statements.balance.loc[Line.OTHER_ASSETS].astype(float),
    ]
    funding = [
        statements.balance.loc[Line.AP].astype(float),
        statements.balance.loc[Line.DEBT].astype(float),
        statements.balance.loc[Line.OTHER_LIAB].astype(float),
        statements.balance.loc[Line.EQUITY].astype(float),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.1))
    for ax in axes:
        _shade_forecast(ax, years, history_end)

    axes[0].stackplot(
        years, *assets,
        labels=["Cash", "AR", "Inventory", "PP&E", "Other"],
        colors=[PALETTE["teal"], PALETTE["blue"], PALETTE["amber"], PALETTE["slate"], "#b0b6c0"],
        alpha=0.9,
    )
    axes[0].set_title("Exhibit C — Assets")
    axes[0].set_ylabel(unit)
    axes[0].legend(loc="upper left", fontsize=7, ncol=2)

    axes[1].stackplot(
        years, *funding,
        labels=["Payables", "Debt", "Other liab.", "Equity"],
        colors=[PALETTE["amber"], PALETTE["coral"], PALETTE["slate"], PALETTE["blue"]],
        alpha=0.9,
    )
    leverage = (
        statements.balance.loc[Line.DEBT].astype(float)
        / statements.balance.loc[Line.EQUITY].astype(float).replace(0, np.nan)
    )
    ax_l = axes[1].twinx()
    ax_l.plot(years, leverage, color=PALETTE["ink"], marker="D", ms=3.5, lw=1.3, label="D/E")
    ax_l.set_ylabel("Debt / Equity")
    ax_l.spines["right"].set_visible(True)
    axes[1].set_title("Exhibit D — Funding and leverage")
    axes[1].set_ylabel(unit)
    lines, labels = axes[1].get_legend_handles_labels()
    lines2, labels2 = ax_l.get_legend_handles_labels()
    axes[1].legend(lines + lines2, labels + labels2, loc="upper left", fontsize=7, ncol=2)
    return _finish(fig)


def plot_cash_bridge(cashflow: pd.DataFrame, unit: str = ""):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_cash_bridge(cashflow, unit)
    years = [int(c) for c in cashflow.columns]
    cfo = cashflow.loc[Line.CFO].astype(float)
    cfi = cashflow.loc[Line.CFI].astype(float)
    cff = cashflow.loc[Line.CFF].astype(float)
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.1))
    x = np.arange(len(years))
    w = 0.26
    axes[0].bar(x - w, cfo, w, label="CFO", color=PALETTE["teal"])
    axes[0].bar(x, cfi, w, label="CFI", color=PALETTE["coral"])
    axes[0].bar(x + w, cff, w, label="CFF", color=PALETTE["blue"])
    axes[0].axhline(0, color=PALETTE["ink"], lw=0.7)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([str(y) for y in years])
    axes[0].set_title("Exhibit E — Cash flow by section")
    axes[0].set_ylabel(unit)
    axes[0].legend(fontsize=8)

    open_c = cashflow.loc[Line.OPEN_CASH].astype(float)
    close_c = cashflow.loc[Line.CLOSE_CASH].astype(float)
    net = cashflow.loc[Line.NET_CHANGE].astype(float)
    axes[1].plot(years, open_c, marker="o", ms=4, color=PALETTE["slate"], label="Opening")
    axes[1].plot(years, close_c, marker="o", ms=4, color=PALETTE["teal"], label="Closing")
    axes[1].bar(years, net, width=0.42, color=[PALETTE["teal"] if v >= 0 else PALETTE["coral"] for v in net], alpha=0.45, label="Net change")
    axes[1].set_title("Exhibit F — Cash rollforward")
    axes[1].set_ylabel(unit)
    axes[1].legend(fontsize=8)
    return _finish(fig)


def plot_working_capital(statements, unit: str = ""):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_working_capital(statements, unit)
    years = [int(c) for c in statements.balance.columns]
    ar = statements.balance.loc[Line.AR].astype(float)
    inv = statements.balance.loc[Line.INVENTORY].astype(float)
    ap = statements.balance.loc[Line.AP].astype(float)
    nwc = ar + inv - ap
    revenue = statements.income.loc[Line.REVENUE].reindex(statements.balance.columns).astype(float)
    nwc_days = (nwc / revenue.replace(0, np.nan)) * 365

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.9))
    axes[0].bar(years, ar, label="Receivables", color=PALETTE["blue"], alpha=0.9)
    axes[0].bar(years, inv, bottom=ar, label="Inventory", color=PALETTE["amber"], alpha=0.9)
    axes[0].bar(years, -ap, label="Payables (−)", color=PALETTE["coral"], alpha=0.9)
    axes[0].plot(years, nwc, color=PALETTE["ink"], marker="o", ms=4, label="Net WC")
    axes[0].axhline(0, color=PALETTE["ink"], lw=0.7)
    axes[0].set_title("Exhibit G — Operating working capital")
    axes[0].set_ylabel(unit)
    axes[0].legend(fontsize=8)

    axes[1].plot(years, nwc_days, marker="o", ms=4, color=PALETTE["blue"])
    axes[1].fill_between(years, nwc_days, alpha=0.12, color=PALETTE["blue"])
    axes[1].set_title("Exhibit H — NWC days of sales")
    axes[1].set_ylabel("Days")
    return _finish(fig)


def plot_audit_heatmap(gaps: pd.DataFrame) -> plt.Figure:
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_audit_heatmap(gaps)
    data = gaps.fillna(0.0).astype(float)
    limit = max(1.0, float(np.nanmax(np.abs(data.values))))
    fig, ax = plt.subplots(figsize=(11.2, max(3.8, 0.3 * len(data))))
    image = ax.imshow(data.values, aspect="auto", cmap=CMAP_DIV, vmin=-limit, vmax=limit)
    ax.set_xticks(range(len(data.columns)))
    ax.set_xticklabels([str(c) for c in data.columns])
    ax.set_yticks(range(len(data.index)))
    ax.set_yticklabels(list(data.index), fontsize=8)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = float(data.values[i, j])
            if abs(value) < 1e-9:
                continue
            ax.text(j, i, f"{value:,.1f}", ha="center", va="center", fontsize=6.5, color=_contrast_text(abs(value), 0, limit))
    ax.set_title("Exhibit I — Statement identity gaps")
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02, label="Gap (millions)")
    return _finish(fig, caption=f"Max |gap| = {float(np.nanmax(np.abs(data.values))):,.2f}. Near-zero means the statements tie.")


# ---------------------------------------------------------------------------
# DCF charts
# ---------------------------------------------------------------------------


def plot_ufcf_waterfall(schedule: pd.DataFrame, unit: str = ""):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_ufcf_waterfall(schedule, unit)
    labels = list(schedule.index.astype(str))
    values = schedule["Present value"].astype(float).tolist()
    factors = schedule["Discount factor"].astype(float).tolist() if "Discount factor" in schedule.columns else [np.nan] * len(values)
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.9), gridspec_kw={"width_ratios": [2.3, 1]})

    bar_colors = [PALETTE["amber"] if label == "Terminal value" else PALETTE["blue"] for label in labels]
    bars = axes[0].bar(range(len(labels)), values, color=bar_colors, width=0.68, edgecolor="white", linewidth=0.5)
    cumulative = np.cumsum(values)
    axes[0].plot(range(len(labels)), cumulative, color=PALETTE["ink"], marker="o", ms=3.5, lw=1.4, label="Cumulative PV")
    for i, (bar, value) in enumerate(zip(bars, values)):
        axes[0].text(bar.get_x() + bar.get_width() / 2, value, f"{value:,.0f}", ha="center", va="bottom" if value >= 0 else "top", fontsize=7.5, color=PALETTE["mute"])
        if np.isfinite(factors[i]):
            axes[0].text(i, min(0, min(values)) * 0.02, f"{factors[i]:.3f}", ha="center", va="top", fontsize=6.2, color=PALETTE["mute"])
    axes[0].set_xticks(range(len(labels)))
    axes[0].set_xticklabels(labels, rotation=15)
    axes[0].set_ylabel(unit)
    axes[0].set_title("Exhibit J — Present value by period")
    axes[0].axhline(0, color=PALETTE["ink"], lw=0.7)
    axes[0].legend(fontsize=8)

    explicit = sum(v for lab, v in zip(labels, values) if lab != "Terminal value")
    terminal = sum(v for lab, v in zip(labels, values) if lab == "Terminal value")
    axes[1].bar(["Explicit", "Terminal"], [explicit, terminal], color=[PALETTE["blue"], PALETTE["amber"]], width=0.55)
    for i, value in enumerate([explicit, terminal]):
        axes[1].text(i, value, f"{value:,.0f}\n{value / (explicit + terminal):.0%}", ha="center", va="bottom", fontsize=8)
    axes[1].set_title("EV composition")
    axes[1].set_ylabel(unit)
    return _finish(fig, caption="Discount factors annotated under each bar. Terminal value uses the final-year discount factor.")


def plot_dcf_pv_split(result):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_dcf_pv_split(result)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    for ax, schedule, title, tv_share, price in (
        (axes[0], result.gordon_schedule, "Gordon growth", result.gordon_tv_share, result.gordon_price),
        (axes[1], result.exit_schedule, "Exit multiple", result.exit_tv_share, result.exit_price),
    ):
        explicit = float(schedule.drop(index="Terminal value")["Present value"].sum())
        terminal = float(schedule.loc["Terminal value", "Present value"])
        bars = ax.bar(["Explicit UFCF", "Terminal"], [explicit, terminal], color=[PALETTE["blue"], PALETTE["amber"]], edgecolor="white", width=0.52)
        for bar, value in zip(bars, [explicit, terminal]):
            ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:,.0f}", ha="center", va="bottom", fontsize=9)
        ax.set_title(f"{title} · TV {tv_share:.0%} of EV · ${price:,.2f}/sh")
        ax.set_ylabel("Present value")
    return _finish(fig)


def steady_state_fcf(case: Case) -> tuple[float, float, str]:
    """Anchor FCFF and EBITDA for surface mapping (latest actuals, not the forecast).

    Cyclical names (e.g. Micron) can produce deeply negative forecast UFCF when
    growth and capex are extrapolated raw. Surfaces use a steady-state FCFF so the
    WACC–g map is the classic textbook shape: V = FCFF₁ / (WACC − g).
    """
    year = case.history.income_years()[-1]
    ebitda = float(case.history.income.loc[Line.EBITDA, year])
    ebit = float(case.history.income.loc[Line.EBIT, year])
    tax = float(case.assumptions.tax_rate)
    g = float(case.assumptions.terminal_growth)
    roic = 0.14
    nopat = max(ebit, 0.40 * max(ebitda, 0.0)) * (1.0 - tax)
    fcf1 = nopat * (1.0 - min(g / roic, 0.85))
    fcf1 = max(fcf1, 0.20 * max(ebitda, 0.0))
    note = (
        f"Surface FCFF₁ = {fcf1:,.1f} from latest-year NOPAT with g/ROIC reinvestment "
        f"(ROIC {roic:.0%}); not the raw forecast UFCF path."
    )
    return fcf1, max(ebitda, 0.0), note


def forecast_dcf_surface(
    case: Case, *, method: str = "gordon", wacc_steps: int = 81,
    terminal_steps: int = 81, wacc_span: float = 0.025,
    growth_span: float = 0.015, multiple_span: float = 4.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Full forecast DCF sensitivity, using the same cash flows and timing as run_dcf.

    The center node is the entered case. Gordon scenarios with WACC <= growth
    are undefined, not clamped to a visually convenient boundary.
    """
    from valuation.dcf import wacc_components

    if method not in {"gordon", "exit"}:
        raise ValueError("method must be 'gordon' or 'exit'")
    if any(not isinstance(n, (int, np.integer)) or n < 3 for n in (wacc_steps, terminal_steps)):
        raise ValueError("Surface dimensions must have at least three grid points")
    if not all(np.isfinite(v) and v > 0 for v in (wacc_span, growth_span, multiple_span)):
        raise ValueError("Surface spans must be finite and positive")
    rate = wacc_components(case)[0]
    terminal = case.assumptions.terminal_growth if method == "gordon" else case.assumptions.exit_ev_ebitda
    if not np.isfinite(rate) or rate <= -1 or not np.isfinite(terminal):
        raise ValueError("Base inputs must be finite and WACC must exceed -100%")
    if not np.isfinite(case.shares) or case.shares <= 0:
        raise ValueError("Shares must be finite and positive")

    def centered_grid(base, span, steps, lower=None):
        low = base-span if lower is None else max(lower, base-span)
        values = np.linspace(low, base+span, steps)
        # Preserve shape and include the exact entered input, even at even resolutions.
        values[np.abs(values-base).argmin()] = base
        return np.sort(values)

    rates = centered_grid(rate, wacc_span, wacc_steps, lower=max(-.99, rate-wacc_span))
    terminals = centered_grid(terminal, growth_span if method == "gordon" else multiple_span, terminal_steps)
    xx, yy = np.meshgrid(rates, terminals)
    forecast = forecast_statements(case).statements
    flows = unlevered_fcf(case, forecast.income, forecast.cashflow).to_numpy(dtype=float)
    if not flows.size:
        raise ValueError("A forecast cash-flow path is required")
    exponents = np.arange(1, len(flows)+1, dtype=float) - (0.5 if case.assumptions.mid_year else 0)
    factors = (1+rates[None, :]) ** -exponents[:, None]
    explicit = flows @ factors
    if method == "gordon":
        terminal_value = np.divide(flows[-1]*(1+yy), xx-yy,
                                   out=np.full_like(xx, np.nan), where=xx > yy)
    else:
        terminal_value = float(forecast.income.loc[Line.EBITDA].iloc[-1]) * yy
    zz = (explicit[None, :] + terminal_value*factors[-1][None, :] - net_debt(case))/case.shares
    return xx, yy, zz


def gordon_price_surface(
    case: Case,
    wacc_steps: int = 81,
    growth_steps: int = 81,
    wacc_span: float = 0.05,
    growth_span: float = 0.025,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Dense WACC × g → $/share from steady-state Gordon (vectorized)."""
    from valuation.dcf import wacc_components

    fcf1, _, _ = steady_state_fcf(case)
    debt = net_debt(case)
    shares = float(case.shares)
    base_wacc = wacc_components(case)[0]
    base_g = float(case.assumptions.terminal_growth)
    waccs = np.linspace(max(0.04, base_wacc - wacc_span), base_wacc + wacc_span, wacc_steps)
    # Keep g strictly below the lowest WACC on the grid for a clean domain.
    g_hi = min(base_g + growth_span, float(waccs.min()) - 0.015)
    g_lo = max(0.0, min(base_g - growth_span, g_hi - 0.01))
    growths = np.linspace(g_lo, g_hi, growth_steps)
    xx, yy = np.meshgrid(waccs, growths)
    spread = xx - yy
    zz = np.where(spread > 1e-4, (fcf1 / spread - debt) / shares, np.nan)
    return xx, yy, zz


def exit_price_surface(
    case: Case,
    wacc_steps: int = 81,
    multiple_steps: int = 81,
    wacc_span: float = 0.05,
    multiple_span: float = 4.0,
    hold_years: int = 5,
    interim_growth: float = 0.06,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Dense WACC × exit multiple → $/share on a steady growing FCFF path."""
    from valuation.dcf import wacc_components

    fcf1, ebitda0, _ = steady_state_fcf(case)
    debt = net_debt(case)
    shares = float(case.shares)
    base_wacc = wacc_components(case)[0]
    base_m = float(case.assumptions.exit_ev_ebitda)
    # Bound exit multiple around a usable teaching range when the market print is extreme.
    base_m = float(np.clip(base_m, 6.0, 18.0))
    waccs = np.linspace(max(0.04, base_wacc - wacc_span), base_wacc + wacc_span, wacc_steps)
    multiples = np.linspace(max(4.0, base_m - multiple_span), base_m + multiple_span, multiple_steps)
    xx, yy = np.meshgrid(waccs, multiples)

    t = np.arange(1, hold_years + 1, dtype=float)
    flows = fcf1 * (1.0 + interim_growth) ** t
    final_ebitda = ebitda0 * (1.0 + interim_growth) ** hold_years

    zz = np.empty_like(xx, dtype=float)
    for i in range(multiple_steps):
        for j in range(wacc_steps):
            rate = float(xx[i, j])
            multiple = float(yy[i, j])
            dfs = 1.0 / (1.0 + rate) ** t
            ev = float(np.dot(flows, dfs) + final_ebitda * multiple * dfs[-1])
            zz[i, j] = (ev - debt) / shares
    return xx, yy, zz


def gordon_surface_mark(case: Case) -> tuple[float, float, float, str]:
    """Base-case (WACC, g, $/sh, note) consistent with ``gordon_price_surface``."""
    from valuation.dcf import wacc_components

    fcf1, _, note = steady_state_fcf(case)
    wacc = wacc_components(case)[0]
    g = float(case.assumptions.terminal_growth)
    price = (fcf1 / (wacc - g) - net_debt(case)) / float(case.shares)
    return wacc, g, price, note


def exit_surface_mark(case: Case, hold_years: int = 5, interim_growth: float = 0.06) -> tuple[float, float, float]:
    """Base-case (WACC, exit multiple, $/sh) consistent with ``exit_price_surface``."""
    from valuation.dcf import wacc_components

    fcf1, ebitda0, _ = steady_state_fcf(case)
    wacc = wacc_components(case)[0]
    multiple = float(np.clip(case.assumptions.exit_ev_ebitda, 6.0, 18.0))
    t = np.arange(1, hold_years + 1, dtype=float)
    flows = fcf1 * (1.0 + interim_growth) ** t
    dfs = 1.0 / (1.0 + wacc) ** t
    final_ebitda = ebitda0 * (1.0 + interim_growth) ** hold_years
    ev = float(np.dot(flows, dfs) + final_ebitda * multiple * dfs[-1])
    price = (ev - net_debt(case)) / float(case.shares)
    return wacc, multiple, price


def _scale_xy(xx, yy, x_as_pct, y_as_pct):
    return (xx * 100 if x_as_pct else xx), (yy * 100 if y_as_pct else yy)


def plot_surface_3d(
    xx, yy, zz, *, xlabel, ylabel, zlabel, title,
    x_as_pct=False, y_as_pct=False, mark=None, cmap=None,
) -> plt.Figure:
    return plot_surface_panel(
        xx, yy, zz, xlabel=xlabel, ylabel=ylabel, zlabel=zlabel, title=title,
        x_as_pct=x_as_pct, y_as_pct=y_as_pct, mark=mark, cmap=cmap,
    )


def plot_surface_panel(
    xx: np.ndarray,
    yy: np.ndarray,
    zz: np.ndarray,
    *,
    xlabel: str,
    ylabel: str,
    zlabel: str,
    title: str,
    x_as_pct: bool = False,
    y_as_pct: bool = False,
    mark: tuple[float, float, float] | None = None,
    cmap=None,
    reference: float | None = None,
    reference_label: str = "Benchmark",
):
    """Sensitivity panel: interactive Plotly 3D + iso-map + base-case slices."""
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_surface_panel(
            xx, yy, zz,
            xlabel=xlabel, ylabel=ylabel, zlabel=zlabel, title=title,
            x_as_pct=x_as_pct, y_as_pct=y_as_pct, mark=mark, cmap=cmap, reference=reference, reference_label=reference_label,
        )
    from valuation.chart_data import _surface_data, _surface_slice
    xx, yy, zz = _surface_data(xx, yy, zz)
    cmap = cmap or CMAP_SURFACE
    if isinstance(cmap, str):
        cmap = plt.get_cmap(cmap)

    x_plot, y_plot = _scale_xy(xx, yy, x_as_pct, y_as_pct)
    finite = zz[np.isfinite(zz)]
    if finite.size == 0:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No finite surface values", ha="center")
        return _finish(fig, title)

    vmin, vmax = float(finite.min()), float(finite.max())
    norm = colors.Normalize(vmin=vmin, vmax=vmax)
    levels = np.linspace(vmin, vmax if vmax > vmin else vmin + max(abs(vmin), 1)*0.01, 10)
    z_floor = vmin - 0.12 * (vmax - vmin if vmax > vmin else 1.0)

    # Light-shaded RGB surface
    ls = LightSource(azdeg=315, altdeg=42)
    zz_filled = np.where(np.isfinite(zz), zz, np.nanmin(finite))
    rgb = ls.shade(zz_filled, cmap=cmap, norm=norm, blend_mode="soft", vert_exag=0.35)

    fig = plt.figure(figsize=(15.2, 10.2))
    gs = GridSpec(2, 2, figure=fig, width_ratios=[1.1, 1.0], height_ratios=[1.6, 1.0],
                  wspace=0.22, hspace=0.38, left=0.07, right=0.94, top=0.90, bottom=0.10)

    ax3d = fig.add_subplot(gs[0, 0], projection="3d", computed_zorder=False)
    ax_map = fig.add_subplot(gs[0, 1])
    ax_sx = fig.add_subplot(gs[1, 0])
    ax_sy = fig.add_subplot(gs[1, 1], sharey=ax_sx)

    surf = ax3d.plot_surface(
        x_plot, y_plot, np.ma.masked_invalid(zz),
        facecolors=rgb, linewidth=0, antialiased=True, shade=False, rstride=1, cstride=1, alpha=0.96,
    )
    ax3d.plot_wireframe(
        x_plot, y_plot, np.ma.masked_invalid(zz),
        rstride=max(1, xx.shape[0] // 10), cstride=max(1, xx.shape[1] // 10),
        color="white", linewidth=0.25, alpha=0.35,
    )
    ax3d.contour(x_plot, y_plot, np.ma.masked_invalid(zz), levels=levels, linewidths=0.55, cmap=cmap, offset=None, alpha=0.75)
    ax3d.contourf(x_plot, y_plot, np.ma.masked_invalid(zz), zdir="z", offset=z_floor, levels=levels, cmap=cmap, alpha=0.55, norm=norm)
    ax3d.contour(x_plot, y_plot, np.ma.masked_invalid(zz), zdir="z", offset=z_floor, levels=levels, colors=PALETTE["ink"], linewidths=0.25, alpha=0.25)

    mx = my = mz = None
    if mark is not None and np.isfinite(mark[2]):
        mx = mark[0] * 100 if x_as_pct else mark[0]
        my = mark[1] * 100 if y_as_pct else mark[1]
        mz = mark[2]
        ax3d.scatter([mx], [my], [mz], color=PALETTE["coral"], s=70, depthshade=False, zorder=10)
        ax3d.plot([mx, mx], [my, my], [z_floor, mz], color=PALETTE["coral"], lw=1.1, ls="--")
        # Base-case slices drawn on the surface
        i_row = int(np.abs(y_plot[:, 0] - my).argmin())
        j_col = int(np.abs(x_plot[0, :] - mx).argmin())
        sx = _surface_slice(y_plot[:, 0], zz, my)
        sy = _surface_slice(x_plot[0, :], zz.T, mx)
        ax3d.plot(x_plot[0, :], np.full(xx.shape[1], my), sx, color=PALETTE["ink"], lw=1.6, alpha=0.95)
        ax3d.plot(np.full(xx.shape[0], mx), y_plot[:, 0], sy, color=PALETTE["amber"], lw=1.6, alpha=0.95)

    ax3d.set_xlabel(xlabel, labelpad=6, fontsize=9)
    ax3d.set_ylabel(ylabel, labelpad=6, fontsize=9)
    ax3d.set_zlabel(zlabel, labelpad=6, fontsize=9)
    ax3d.set_title("Shaded surface with iso-contours", fontsize=10, pad=8)
    ax3d.view_init(elev=26, azim=-52)
    ax3d.set_zlim(z_floor, vmax + 0.06 * (vmax - vmin if vmax > vmin else 1))
    for axis in (ax3d.xaxis, ax3d.yaxis, ax3d.zaxis):
        axis.pane.fill = False
        axis.pane.set_edgecolor(PALETTE["fog"])
    ax3d.grid(True, alpha=0.2)
    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array([])
    # The iso-map supplies the shared color key for both views.

    # Contour map + crosshair
    cf = ax_map.contourf(x_plot, y_plot, zz, levels=levels, cmap=cmap, norm=norm)
    cs = ax_map.contour(x_plot, y_plot, zz, levels=levels, colors=PALETTE["ink"], linewidths=0.45, alpha=0.55)
    ax_map.clabel(cs, inline=True, fontsize=6.5, fmt="%.1f")
    if mx is not None:
        ax_map.axvline(mx, color=PALETTE["coral"], ls="--", lw=0.9, alpha=0.85)
        ax_map.axhline(my, color=PALETTE["amber"], ls="--", lw=0.9, alpha=0.85)
        ax_map.plot(mx, my, marker="*", markersize=13, color=PALETTE["coral"], markeredgecolor="white", markeredgewidth=0.7)
        ax_map.annotate(
            f"Base {mz:,.2f}",
            (mx, my), textcoords="offset points", xytext=(12, -20), ha="left",
            fontsize=8, color=PALETTE["coral"], fontweight="bold",
            arrowprops={"arrowstyle": "->", "color": PALETTE["coral"], "lw": 0.8},
        )
    if reference is not None and np.isfinite(reference):
        if vmin < reference < vmax:
            threshold = ax_map.contour(x_plot, y_plot, zz, levels=[reference], colors=[T.NEG], linewidths=1.6)
            ax_map.clabel(threshold, fmt={reference: f"{reference_label} {reference:,.2f}"}, fontsize=8)
        for axis in (ax_sx, ax_sy):
            axis.axhline(reference, color=T.NEG, ls="--", lw=1, label=reference_label)
    ax_map.set_xlabel(xlabel)
    ax_map.set_ylabel(ylabel)
    ax_map.set_title("Iso-value map", fontsize=10)
    fig.colorbar(cf, ax=ax_map, fraction=0.046, pad=0.03, label=zlabel)

    # Independent input scales and a common output scale for honest comparisons.
    if mx is None:
        mx, my = float(np.median(x_plot[0])), float(np.median(y_plot[:, 0]))
        sx = _surface_slice(y_plot[:, 0], zz, my)
        sy = _surface_slice(x_plot[0], zz.T, mx)
    for ax, coords, values, color, varying, fixed, fixed_value, base_input in (
        (ax_sx, x_plot[0], sx, T.ACCENT, xlabel, ylabel, my, mx),
        (ax_sy, y_plot[:, 0], sy, T.WARM, ylabel, xlabel, mx, my),
    ):
        fixed_axis, grid = (y_plot[:, 0], zz) if ax is ax_sx else (x_plot[0], zz.T)
        for fraction in (.25, .75):
            at = fixed_axis[0] + np.ptp(fixed_axis)*fraction
            ax.plot(coords, _surface_slice(fixed_axis, grid, at), color=color,
                    lw=1.0, ls=":", alpha=.45)
        ax.plot(coords, values, color=color, lw=2.2)
        ax.set_xlabel(varying)
        ax.set_ylabel(zlabel)
        ax.set_title(f"{varying} sensitivity", loc="left", fontsize=11, pad=22)
        ax.text(0, 1.02, f"{fixed} held at {fixed_value:.2f}", transform=ax.transAxes,
                fontsize=9, color=T.MUTE)
        ax.axvline(base_input, color=color, ls=":", lw=.9, alpha=.65)
        if mz is not None:
            ax.axhline(mz, color=T.NEG, ls=":", lw=1)
            ax.scatter([base_input], [mz], color=T.NEG, s=28, zorder=5)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(False, axis="x")
    pad = max(vmax - vmin, 1) * .06
    ax_sx.set_ylim(vmin-pad, vmax+pad)

    span = vmax - vmin
    stats = f"min {vmin:,.2f}  ·  max {vmax:,.2f}  ·  range {span:,.2f}"
    if mz is not None:
        stats += f"  ·  base {mz:,.2f}"
    fig.suptitle(title, fontsize=13, fontweight="bold", color=PALETTE["ink"], y=0.97)
    fig.text(0.5, 0.02, stats + "   |   Blue / amber: input slices  ·  Dotted curves: alternate assumptions  ·  Red dot: base case",
             ha="center", fontsize=8, color=PALETTE["mute"])
    # Keep a reference so linters/tools see surf used
    _ = surf
    return fig


def plot_heatmap(
    frame: pd.DataFrame,
    title: str,
    cbar_label: str = "",
    *,
    base_row: str | None = None,
    base_col: str | None = None,
    delta: bool = False,
    fmt: str = "{:.1f}",
    cmap=None,
):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_heatmap(
            frame, title, cbar_label,
            base_row=base_row, base_col=base_col, delta=delta, fmt=fmt, cmap=cmap,
        )
    data = frame.astype(float)
    base_value = None
    if base_row is not None and base_col is not None and base_row in data.index and base_col in data.columns:
        base_value = float(data.loc[base_row, base_col])
    display = data - base_value if (delta and base_value is not None and np.isfinite(base_value)) else data.copy()
    use_cmap = CMAP_DIV if delta else (cmap or CMAP_SEQ)
    if delta and base_value is not None:
        title = f"{title} (Δ vs base {fmt.format(base_value)})"

    finite = display.values[np.isfinite(display.values)]
    fig, ax = plt.subplots(figsize=(10.8, max(4.4, 0.42 * len(display) + 1.6)))
    if finite.size == 0:
        ax.text(0.5, 0.5, "No data", ha="center")
        return _finish(fig, title)

    if delta:
        limit = max(abs(finite.min()), abs(finite.max()), 1e-9)
        image = ax.imshow(display.values, aspect="auto", cmap=use_cmap, norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit))
    else:
        image = ax.imshow(display.values, aspect="auto", cmap=use_cmap)

    ax.set_xticks(range(len(display.columns)))
    ax.set_xticklabels(list(display.columns), rotation=30, ha="right")
    ax.set_yticks(range(len(display.index)))
    ax.set_yticklabels(list(display.index))
    ax.set_title(title)
    ax.set_xticks(np.arange(-0.5, display.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, display.shape[0], 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)

    vmin, vmax = float(np.nanmin(display.values)), float(np.nanmax(display.values))
    for i in range(display.shape[0]):
        for j in range(display.shape[1]):
            value = display.values[i, j]
            if not np.isfinite(value):
                ax.text(j, i, "—", ha="center", va="center", color=PALETTE["mute"], fontsize=8)
                continue
            ref = abs(value) if delta else value
            lo, hi = (0, max(abs(vmin), abs(vmax))) if delta else (vmin, vmax)
            ax.text(j, i, fmt.format(value), ha="center", va="center", color=_contrast_text(ref, lo, hi), fontsize=8)

    if base_row in display.index and base_col in display.columns:
        bi, bj = list(display.index).index(base_row), list(display.columns).index(base_col)
        ax.add_patch(plt.Rectangle((bj - 0.5, bi - 0.5), 1, 1, fill=False, edgecolor=PALETTE["coral"], lw=2.0))

    cbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label(cbar_label or ("Δ" if delta else ""))
    return _finish(
        fig,
        caption=f"min {np.nanmin(display.values):.2f} · median {np.nanmedian(display.values):.2f} · max {np.nanmax(display.values):.2f}",
    )


def plot_sensitivity_pair(
    frame: pd.DataFrame,
    title: str,
    cbar_label: str = "",
    *,
    base_row: str | None = None,
    base_col: str | None = None,
    fmt: str = "{:.1f}",
):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_sensitivity_pair(
            frame, title, cbar_label,
            base_row=base_row, base_col=base_col, fmt=fmt,
        )
    data = frame.astype(float)
    fig, axes = plt.subplots(1, 2, figsize=(14.2, max(4.6, 0.4 * len(data) + 1.5)))
    base_value = None
    if base_row in data.index and base_col in data.columns:
        base_value = float(data.loc[base_row, base_col])

    for ax, delta, sub, cmap in (
        (axes[0], False, "Level", CMAP_SEQ),
        (axes[1], True, "Change versus base", CMAP_DIV),
    ):
        display = (data - base_value) if (delta and base_value is not None) else data.copy()
        finite = display.values[np.isfinite(display.values)]
        if delta and finite.size:
            limit = max(abs(finite.min()), abs(finite.max()), 1e-9)
            image = ax.imshow(
                display.values,
                aspect="auto",
                cmap=cmap,
                norm=TwoSlopeNorm(vcenter=0.0, vmin=-limit, vmax=limit),
            )
        else:
            image = ax.imshow(display.values, aspect="auto", cmap=cmap)
        ax.set_xticks(range(len(display.columns)))
        ax.set_xticklabels(list(display.columns), rotation=30, ha="right", fontsize=8)
        ax.set_yticks(range(len(display.index)))
        ax.set_yticklabels(list(display.index), fontsize=8)
        ax.set_title(sub)
        ax.set_xticks(np.arange(-0.5, display.shape[1], 1), minor=True)
        ax.set_yticks(np.arange(-0.5, display.shape[0], 1), minor=True)
        ax.grid(which="minor", color="white", lw=1.0)
        ax.tick_params(which="minor", bottom=False, left=False)
        vmin, vmax = float(np.nanmin(display.values)), float(np.nanmax(display.values))
        for i in range(display.shape[0]):
            for j in range(display.shape[1]):
                value = display.values[i, j]
                if not np.isfinite(value):
                    continue
                ref = abs(value) if delta else value
                lo, hi = (0, max(abs(vmin), abs(vmax))) if delta else (vmin, vmax)
                ax.text(j, i, fmt.format(value), ha="center", va="center", color=_contrast_text(ref, lo, hi), fontsize=7.5)
        if base_row in display.index and base_col in display.columns:
            bi, bj = list(display.index).index(base_row), list(display.columns).index(base_col)
            ax.add_patch(plt.Rectangle((bj - 0.5, bi - 0.5), 1, 1, fill=False, edgecolor=PALETTE["coral"], lw=1.8))
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.03, label=cbar_label if not delta else f"Δ {cbar_label}")

    fig.suptitle(title, fontsize=12.5, fontweight="bold", color=PALETTE["ink"])
    fig.subplots_adjust(left=0.08, right=0.96, top=0.88, bottom=0.12, wspace=0.22)
    return fig


# ---------------------------------------------------------------------------
# Comps / LBO / SOTP / bridge
# ---------------------------------------------------------------------------


def plot_comps_dashboard(comps_result, case: Case):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_comps_dashboard(comps_result, case)
    fig = plt.figure(figsize=(12.8, 8.4))
    gs = GridSpec(2, 2, figure=fig, hspace=0.36, wspace=0.28, left=0.1, right=0.97, top=0.9, bottom=0.08)
    ax0, ax1, ax2 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])
    peers = comps_result.peers
    if peers.empty:
        for ax in (ax0, ax1, ax2):
            ax.text(0.5, 0.5, "No peers loaded", ha="center")
            ax.axis("off")
        return _finish(fig, "Trading comps")

    def _peer_bar(ax, series, subject_value, title, xlabel):
        order = series.sort_values()
        bars = ax.barh(peers.loc[order.index, "name"].astype(str), order, color=PALETTE["blue"])
        for bar, value in zip(bars, order):
            ax.text(value, bar.get_y() + bar.get_height() / 2, f" {value:.1f}x", va="center", fontsize=8, color=PALETTE["mute"])
        if np.isfinite(subject_value):
            ax.axvline(subject_value, color=PALETTE["coral"], ls="--", lw=1.2, label=f"Subject {subject_value:.1f}x")
        ax.axvline(float(series.median()), color=PALETTE["amber"], ls=":", lw=1.2, label=f"Median {series.median():.1f}x")
        ax.set_xlabel(xlabel)
        ax.set_title(title)
        ax.legend(fontsize=8)

    _peer_bar(ax0, peers["ev_ebitda"].astype(float), float(comps_result.subject.loc[0, "ev_ebitda"]), "Peer EV/EBITDA", "×")
    _peer_bar(ax1, peers["ev_sales"].astype(float), float(comps_result.subject.loc[0, "ev_sales"]), "Peer EV/Sales", "×")

    implied = comps_result.implied.reset_index(drop=True)
    for i, row in implied.iterrows():
        ax2.plot([row["price_low"], row["price_high"]], [i, i], color=PALETTE["blue"], lw=4.5, solid_capstyle="round")
        ax2.plot(row["price_mid"], i, "o", color=PALETTE["ink"], ms=8)
        ax2.plot([row["price_low"], row["price_high"]], [i, i], "o", color=PALETTE["blue"], ms=5)
        ax2.text(row["price_low"], i + 0.2, f"{row['price_low']:.1f}", ha="center", fontsize=7, color=PALETTE["mute"])
        ax2.text(row["price_mid"], i + 0.2, f"{row['price_mid']:.1f}", ha="center", fontsize=8, color=PALETTE["ink"], fontweight="bold")
        ax2.text(row["price_high"], i + 0.2, f"{row['price_high']:.1f}", ha="center", fontsize=7, color=PALETTE["mute"])
    ax2.set_yticks(range(len(implied)))
    ax2.set_yticklabels(implied["method"])
    if case.price is not None:
        ax2.axvline(case.price, color=PALETTE["coral"], ls="--", label=f"Market {case.price:.2f}")
        ax2.legend(fontsize=8)
    ax2.set_xlabel("Implied price per share")
    ax2.set_title("Implied range (min → max; center = median)")
    fig.suptitle("Trading comps", fontsize=12.5, fontweight="bold", color=PALETTE["ink"])
    return fig


def plot_sources_uses(sources_uses: pd.DataFrame, unit: str = "") -> plt.Figure:
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_sources_uses(sources_uses, unit)
    frame = sources_uses[~sources_uses["item"].str.startswith("Total")].copy()
    uses = frame[frame["side"] == "use"].sort_values("amount")
    sources = frame[frame["side"] == "source"].sort_values("amount")
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.0))
    for ax, data, color, title in (
        (axes[0], uses, PALETTE["coral"], "Uses"),
        (axes[1], sources, PALETTE["teal"], "Sources"),
    ):
        bars = ax.barh(data["item"], data["amount"], color=color)
        total = float(data["amount"].sum())
        for bar, value in zip(bars, data["amount"]):
            ax.text(value, bar.get_y() + bar.get_height() / 2, f" {value:,.1f} ({value / total:.0%})", va="center", fontsize=8, color=PALETTE["mute"])
        ax.set_title(f"{title} · {total:,.1f}")
        ax.set_xlabel(unit)
    return _finish(fig)


def plot_debt_stack(schedule: pd.DataFrame, unit: str = ""):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_debt_stack(schedule, unit)
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.0))
    years = schedule["year"]
    axes[0].stackplot(
        years, schedule["revolver"], schedule["term"], schedule["notes"],
        labels=["Revolver", "Term", "Notes"],
        colors=[PALETTE["amber"], PALETTE["blue"], PALETTE["slate"]], alpha=0.9,
    )
    axes[0].plot(years, schedule["cash"], color=PALETTE["ink"], marker="o", ms=4, label="Cash")
    axes[0].plot(years, schedule["net_debt"], color=PALETTE["coral"], marker="s", ms=3.5, ls="--", label="Net debt")
    axes[0].set_title("Debt stack and net debt")
    axes[0].set_ylabel(unit)
    axes[0].legend(fontsize=8)

    hold = schedule[schedule["phase"] == "hold"]
    if not hold.empty:
        axes[1].bar(hold["year"] - 0.15, hold["mandatory"], width=0.28, label="Mandatory", color=PALETTE["coral"])
        axes[1].bar(hold["year"] + 0.15, hold["sweep"], width=0.28, label="Sweep", color=PALETTE["teal"])
        axes[1].plot(hold["year"], hold["interest"], color=PALETTE["ink"], marker="o", ms=4, label="Interest")
        axes[1].plot(hold["year"], hold["ebitda"], color=PALETTE["blue"], marker="D", ms=3.5, ls=":", label="EBITDA")
        axes[1].set_title("Debt service versus EBITDA")
        axes[1].set_ylabel(unit)
        axes[1].legend(fontsize=8)
    return _finish(fig)


def plot_returns_bridge(bridge: pd.DataFrame, unit: str = "") -> plt.Figure:
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_returns_bridge(bridge, unit)
    wanted = [
        "Entry firm equity",
        "EBITDA growth at the exit multiple",
        "Multiple change on entry EBITDA",
        "Deleveraging",
        "Exit firm equity",
    ]
    frame = bridge.set_index("item").loc[wanted, "amount"].astype(float)
    fig, ax = plt.subplots(figsize=(11.5, 4.9))
    running = 0.0
    xs, bottoms, heights, cols, labels = [], [], [], [], []
    for name, value in frame.items():
        if name in ("Entry firm equity", "Exit firm equity"):
            bottoms.append(0.0)
            heights.append(value)
            running = value
            cols.append(PALETTE["blue"] if name.startswith("Entry") else PALETTE["teal"])
        else:
            bottoms.append(running if value >= 0 else running + value)
            heights.append(abs(value))
            running += value
            cols.append(PALETTE["teal"] if value >= 0 else PALETTE["coral"])
        xs.append(name.replace(" at the exit multiple", "").replace(" on entry EBITDA", ""))
        labels.append(value)
    ax.bar(range(len(xs)), heights, bottom=bottoms, color=cols, width=0.62, edgecolor="white")
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels(xs, rotation=15, ha="right")
    for i, value in enumerate(labels):
        ax.text(i, bottoms[i] + heights[i], f"{value:,.0f}", ha="center", va="bottom", fontsize=8, color=PALETTE["mute"])
    ax.set_ylabel(unit)
    ax.set_title("Returns bridge — firm equity")
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    return _finish(fig, caption="Fees sit outside this bridge, between firm equity and the sponsor check.")


def lbo_irr_surface(
    case: Case,
    entry_steps: int = 61,
    exit_steps: int = 61,
    entry_span: float = 3.0,
    exit_span: float = 3.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    base_entry = float(np.clip(case.assumptions.lbo.entry_ev_ebitda, 6.0, 16.0))
    base_exit = float(np.clip(case.assumptions.lbo.exit_ev_ebitda, 6.0, 16.0))
    entries = np.linspace(max(4.0, base_entry - entry_span), base_entry + entry_span, entry_steps)
    exits = np.linspace(max(4.0, base_exit - exit_span), base_exit + exit_span, exit_steps)
    xx, yy = np.meshgrid(entries, exits)
    zz = np.full_like(xx, np.nan, dtype=float)
    for i in range(exit_steps):
        for j in range(entry_steps):
            trial_lbo = replace(case.assumptions.lbo, entry_ev_ebitda=float(xx[i, j]), exit_ev_ebitda=float(yy[i, j]))
            trial = replace(case, assumptions=replace(case.assumptions, lbo=trial_lbo))
            outcome = run_lbo(trial)
            zz[i, j] = np.nan if outcome.irr is None else outcome.irr * 100.0
    return xx, yy, zz


def plot_composition(labels, values, *, title: str = "Composition", hole: float = 0.62):
    """Donut / composition chart (research style)."""
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_composition(labels, values, title=title, hole=hole)
    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    ax.pie(
        [max(0.0, float(v)) for v in values],
        labels=[str(x) for x in labels],
        autopct="%1.0f%%",
        colors=SERIES[: len(list(labels))],
        startangle=90,
        wedgeprops={"edgecolor": T.PAPER, "linewidth": 1.5, "width": 1 - hole},
    )
    ax.set_title(title)
    return _finish(fig)


def plot_sotp_waterfall(by_segment: pd.DataFrame, net_debt: float, equity: float, unit: str = ""):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_sotp_waterfall(by_segment, net_debt, equity, unit)
    rows = list(by_segment.to_dict(orient="records"))
    labels = [r["segment"] for r in rows] + ["Net debt", "Equity value"]
    values = [float(r["enterprise_value"]) for r in rows] + [-net_debt, equity]
    fig, ax = plt.subplots(figsize=(11.8, 5.0))
    running = 0.0
    for i, (label, value) in enumerate(zip(labels, values)):
        if label == "Equity value":
            ax.bar(i, value, color=PALETTE["teal"], width=0.62, edgecolor="white")
            ax.text(i, value, f"{value:,.0f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
            continue
        color = PALETTE["amber"] if ("discount" in label.lower() or "corporate" in label.lower()) else (
            PALETTE["coral"] if value < 0 else PALETTE["blue"]
        )
        bottom = running if value >= 0 else running + value
        ax.bar(i, abs(value), bottom=bottom, color=color, width=0.62, edgecolor="white")
        running += value
        ax.text(i, running, f"{value:,.0f}", ha="center", va="bottom", fontsize=8, color=PALETTE["mute"])
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel(unit)
    ax.set_title("Sum of the parts → equity value")
    ax.axhline(0, color=PALETTE["ink"], lw=0.7)
    return _finish(fig)


def plot_football_field(bridge: pd.DataFrame, market_price: float | None = None):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_football_field(bridge, market_price=market_price)
    plot = bridge.dropna(subset=["mid"]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(11.5, max(4.4, 0.58 * len(plot) + 1.6)))
    for i, row in plot.iterrows():
        ax.plot([row["low"], row["high"]], [i, i], color=PALETTE["blue"], lw=4.5, solid_capstyle="round")
        ax.plot(row["mid"], i, "o", color=PALETTE["ink"], ms=8)
        ax.plot([row["low"], row["high"]], [i, i], "o", color=PALETTE["blue"], ms=5)
        ax.text(row["low"], i + 0.2, f"{row['low']:.1f}", ha="center", fontsize=7, color=PALETTE["mute"])
        ax.text(row["mid"], i + 0.2, f"{row['mid']:.1f}", ha="center", fontsize=8, color=PALETTE["ink"], fontweight="bold")
        ax.text(row["high"], i + 0.2, f"{row['high']:.1f}", ha="center", fontsize=7, color=PALETTE["mute"])
        if market_price is not None and np.isfinite(row["mid"]):
            ax.text(float(row["high"]), i - 0.22, f"  {float(row['mid']) - market_price:+.1f} vs mkt", ha="left", fontsize=7, color=PALETTE["mute"])
    ax.set_yticks(range(len(plot)))
    ax.set_yticklabels(plot["method"])
    xs = plot[["low", "mid", "high"]].astype(float)
    lo, hi = float(xs.min().min()), float(xs.max().max())
    pad = 0.08 * (hi - lo if hi > lo else 1)
    ax.set_xlim(lo - pad, hi + pad * 2.4)
    if market_price is not None:
        ax.axvline(market_price, color=PALETTE["coral"], ls="--", lw=1.4, label=f"Market {market_price:.2f}")
        ax.legend(loc="lower right")
    ax.set_xlabel("Equity value per share")
    ax.set_title("Valuation bridge")
    return _finish(fig, caption="Disagreement across methods is the output. Do not average into a false precision.")


def plot_method_bars(bridge: pd.DataFrame, market_price: float | None = None):
    if _use_plotly():
        from valuation import plotly_charts as pc

        return pc.plot_method_bars(bridge, market_price=market_price)
    plot = bridge.dropna(subset=["mid"]).copy().iloc[::-1]
    fig, ax = plt.subplots(figsize=(10.8, max(4.2, 0.42 * len(plot) + 1.4)))
    colors_bar = [PALETTE["coral"] if m == "Market price" else PALETTE["blue"] for m in plot["method"]]
    bars = ax.barh(plot["method"], plot["mid"], color=colors_bar, edgecolor="white")
    for bar, value in zip(bars, plot["mid"]):
        label = f" {value:,.2f}"
        if market_price is not None:
            label += f"  ({value - market_price:+.1f})"
        ax.text(value, bar.get_y() + bar.get_height() / 2, label, va="center", fontsize=8, color=PALETTE["mute"])
    if market_price is not None:
        ax.axvline(market_price, color=PALETTE["coral"], ls="--", label=f"Market {market_price:.2f}")
        ax.legend()
    ax.set_xlabel("Mid equity value per share")
    ax.set_title("Point estimates by method")
    return _finish(fig)


def nearest_label(labels, target: float, *, as_pct: bool = False, as_multiple: bool = False) -> str:
    best, best_dist = None, float("inf")
    for label in labels:
        text = str(label).strip().replace("%", "").replace("x", "")
        try:
            value = float(text) / 100.0 if as_pct else float(text)
        except ValueError:
            continue
        dist = abs(value - target)
        if dist < best_dist:
            best_dist, best = dist, str(label)
    return best if best is not None else str(list(labels)[0])
