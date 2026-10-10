"""Firm-style output tables for notebooks.

Each model returns a small result card: headline metrics, then supporting detail.
Charts stay in plots.py; this module is the printed summary above the figure.

Colors use VS Code / Jupyter CSS variables so cards stay legible on dark themes.
"""

from __future__ import annotations

from typing import Any

from IPython.display import HTML, Markdown, display
import pandas as pd

from valuation.case import Case

# Theme tokens — Cursor/VS Code dark first, Jupyter second, light fallback last.
_FG = "var(--vscode-editor-foreground, var(--jp-content-font-color1, #e8eaed))"
_MUTE = "var(--vscode-descriptionForeground, var(--jp-content-font-color2, #a8b0bc))"
_CARD = "var(--vscode-editorWidget-background, var(--jp-layout-color1, #2a2d33))"
_BORDER = "var(--vscode-panel-border, var(--jp-border-color1, #3c4450))"
_ACCENT = "var(--vscode-textLink-foreground, var(--jp-info-color, #6cb6ff))"
_WARN_BG = "var(--vscode-inputValidation-warningBackground, rgba(180,140,40,0.15))"
_WARN_BD = "var(--vscode-inputValidation-warningBorder, #a88b2d)"
_FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
_SERIF = "Helvetica Neue, Helvetica, Arial, sans-serif"


def _fmt(value, kind: str = "num") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if kind == "price":
        return f"${float(value):,.2f}"
    if kind == "pct":
        return f"{float(value):.1%}"
    if kind == "pct2":
        return f"{float(value):.2%}"
    if kind == "x":
        return f"{float(value):.2f}x"
    if kind == "int":
        return f"{int(value):,}"
    if kind == "num0":
        return f"{float(value):,.0f}"
    if kind == "num1":
        return f"{float(value):,.1f}"
    return str(value)


def section(title: str, subtitle: str | None = None) -> None:
    body = (
        f"<div style='border-top:1.5px solid {_BORDER};margin:1.4em 0 0.6em 0;padding-top:0.45em'>"
        f"<div style='font-family:{_SERIF};font-size:1.3rem;color:{_FG};letter-spacing:0.01em;"
        f"font-weight:600'>{title}</div>"
    )
    if subtitle:
        body += (
            f"<div style='font-family:{_FONT};font-size:0.9rem;color:{_MUTE};"
            f"margin-top:0.25em;line-height:1.4'>{subtitle}</div>"
        )
    body += "</div>"
    display(HTML(body))


def kpi_row(items: list[tuple[str, str]]) -> None:
    cells = []
    for label, value in items:
        cells.append(
            f"<div style='flex:1;min-width:120px;padding:0.65em 0.75em;border:1px solid {_BORDER};"
            f"background:{_CARD};margin:0.15em;border-radius:2px'>"
            f"<div style='font-family:{_FONT};font-size:0.72rem;color:{_MUTE};"
            f"text-transform:uppercase;letter-spacing:0.07em'>{label}</div>"
            f"<div style='font-family:{_SERIF};font-size:1.4rem;color:{_FG};margin-top:0.2em;"
            f"font-weight:600'>{value}</div>"
            "</div>"
        )
    display(HTML("<div style='display:flex;flex-wrap:wrap;gap:0'>" + "".join(cells) + "</div>"))


def note(text: str) -> None:
    display(HTML(
        f"<div style='font-family:{_FONT};font-size:0.88rem;color:{_MUTE};"
        f"border-left:2px solid {_ACCENT};padding:0.4em 0.75em;margin:0.5em 0;"
        f"line-height:1.45'>{text}</div>"
    ))


def warnings_box(warnings: list[str], *, title: str = "Notes", limit: int | None = None) -> None:
    if not warnings:
        return
    rows = warnings if limit is None else warnings[:limit]
    items = "".join(f"<li style='margin:0.2em 0;line-height:1.4'>{w}</li>" for w in rows)
    extra = ""
    if limit is not None and len(warnings) > limit:
        extra = (
            f"<div style='margin-top:0.35em;color:{_MUTE};font-size:0.8rem'>"
            f"+{len(warnings) - limit} more in case.warnings</div>"
        )
    display(HTML(
        f"<div style='font-family:{_FONT};font-size:0.88rem;color:{_FG};"
        f"background:{_WARN_BG};border:1px solid {_WARN_BD};padding:0.7em 0.9em;margin:0.6em 0;"
        f"border-radius:2px'>"
        f"<strong style='color:{_FG}'>{title}</strong>"
        f"<ul style='margin:0.4em 0 0 1.1em;padding:0'>{items}</ul>{extra}</div>"
    ))


def table(frame: pd.DataFrame, digits: int = 1, caption: str | None = None) -> None:
    styled = (
        frame.round(digits)
        .style.set_table_styles(
            [
                {"selector": "th", "props": [
                    ("font-family", "Helvetica Neue, Helvetica, Arial, sans-serif"),
                    ("font-size", "0.8rem"),
                    ("font-weight", "600"),
                    ("color", "var(--vscode-editor-foreground, var(--jp-content-font-color1, #e8eaed))"),
                    ("border-bottom", "1.5px solid var(--vscode-panel-border, #3c4450)"),
                    ("background", "var(--vscode-editorWidget-background, #2a2d33)"),
                    ("text-align", "right"),
                    ("padding", "0.4em 0.6em"),
                ]},
                {"selector": "td", "props": [
                    ("font-family", "Helvetica Neue, Helvetica, Arial, sans-serif"),
                    ("font-size", "0.85rem"),
                    ("color", "var(--vscode-editor-foreground, var(--jp-content-font-color1, #e8eaed))"),
                    ("border-bottom", "1px solid var(--vscode-panel-border, #3c4450)"),
                    ("text-align", "right"),
                    ("padding", "0.35em 0.6em"),
                ]},
                {"selector": "th:first-child, td:first-child", "props": [("text-align", "left")]},
                {"selector": "caption", "props": [
                    ("font-family", "Helvetica Neue, Helvetica, Arial, sans-serif"),
                    ("font-size", "0.8rem"),
                    ("color", "var(--vscode-descriptionForeground, #a8b0bc)"),
                    ("text-align", "left"),
                    ("caption-side", "bottom"),
                    ("padding-top", "0.4em"),
                ]},
            ]
        )
    )
    if caption:
        styled = styled.set_caption(caption)
    display(styled)


def case_banner(case: Case) -> None:
    source = "Synthetic teaching case" if case.synthetic else f"Live map · {case.source}"
    price = "—" if case.price is None else _fmt(case.price, "price")
    section(
        case.name,
        f"{source} · ticker {case.ticker or '—'} · {case.timing_note}",
    )
    kpi_row([
        ("Price", price),
        ("Shares (m)", _fmt(case.shares, "num1")),
        ("Unit", case.unit),
        ("Peers", str(len(case.peers))),
        ("Segments", str(len(case.segments))),
    ])
    warnings_box(
        case.warnings,
        title="Mapping notes — read before treating a live run as analysis",
        limit=4,
    )


def show_active_card(case: Case, spec: dict[str, Any] | None = None) -> None:
    """Compact, high-contrast card for the active-case notebook."""
    from valuation.active import resolve_active

    spec = spec or resolve_active()
    price = "—" if case.price is None else _fmt(case.price, "price")
    peers = ", ".join(spec.get("peers") or []) or "—"
    ticker = spec.get("ticker") or case.ticker or "—"
    body = f"""
    <div style="font-family:{_FONT};border:1px solid {_BORDER};background:{_CARD};
                border-radius:4px;padding:1em 1.15em;margin:0.4em 0 0.8em 0">
      <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:0.6em;align-items:baseline">
        <div style="font-family:{_SERIF};font-size:1.45rem;color:{_FG};font-weight:600">
          {case.name}
        </div>
        <div style="font-size:0.85rem;color:{_ACCENT};letter-spacing:0.04em">
          PRESET · {spec.get('preset', '—').upper()}
        </div>
      </div>
      <div style="margin-top:0.35em;font-size:0.92rem;color:{_MUTE};line-height:1.45">
        Ticker <strong style="color:{_FG}">{ticker}</strong>
        · Price <strong style="color:{_FG}">{price}</strong>
        · Unit <strong style="color:{_FG}">{case.unit}</strong>
        · Shares <strong style="color:{_FG}">{_fmt(case.shares, 'num1')}m</strong>
      </div>
      <div style="margin-top:0.45em;font-size:0.85rem;color:{_MUTE};line-height:1.4">
        Peers: <span style="color:{_FG}">{peers}</span>
        · Segments: <span style="color:{_FG}">{len(case.segments)}</span>
      </div>
    </div>
    """
    display(HTML(body))
    warnings_box(case.warnings[1:], title="Notes", limit=3)


def show_dcf(result, case: Case) -> None:
    section("DCF output", "Unlevered free cash flow · WACC · two terminal conventions")
    kpi_row([
        ("WACC", _fmt(result.wacc, "pct2")),
        ("Gordon $/sh", _fmt(result.gordon_price, "price")),
        ("Exit-mult $/sh", _fmt(result.exit_price, "price")),
        ("Gordon TV share", _fmt(result.gordon_tv_share, "pct")),
        ("Exit TV share", _fmt(result.exit_tv_share, "pct")),
        ("Net debt", _fmt(result.net_debt, "num1")),
    ])
    detail = pd.DataFrame(
        {
            "Cost of equity": [result.cost_of_equity],
            "After-tax kd": [result.after_tax_cost_of_debt],
            "Equity weight": [result.equity_weight],
            "Debt weight": [result.debt_weight],
            "Gordon EV": [result.gordon_enterprise_value],
            "Exit EV": [result.exit_enterprise_value],
            "Market price": [case.price],
        },
        index=["Base case"],
    )
    table(detail, digits=3, caption=result.weight_note)
    warnings_box(result.warnings)


def show_comps(result, case: Case) -> None:
    section("Comps output", result.basis_note)
    if result.implied.empty:
        warnings_box(result.warnings or ["No implied prices — pass PEERS."], title="Comps")
        return
    mid = result.implied.set_index("method")
    kpis = []
    for method in mid.index:
        kpis.append((str(method), _fmt(mid.loc[method, "price_mid"], "price")))
    if case.price is not None:
        kpis.insert(0, ("Market", _fmt(case.price, "price")))
    kpi_row(kpis[:6])
    table(result.peers, digits=2, caption="Peer multiples (outliers retained)")
    table(result.stats, digits=2, caption="Peer distribution")
    table(result.implied, digits=2, caption="Implied equity value and price from peer min / median / max")
    warnings_box(result.warnings)


def show_lbo(result, case: Case) -> None:
    section("LBO output", "Debt sized on EBITDA · fees outside the company · exit EV − ending net debt")
    kpi_row([
        ("Entry multiple", _fmt(result.entry_multiple, "x")),
        ("Entry EV", _fmt(result.entry_ev, "num1")),
        ("Sponsor equity", _fmt(result.sponsor_equity, "num1")),
        ("IRR", _fmt(result.irr, "pct") if result.irr is not None else "—"),
        ("MOIC", _fmt(result.moic, "x") if result.moic is not None else "—"),
        ("Exit equity", _fmt(result.exit_equity, "num1")),
    ])
    detail = pd.DataFrame(
        {
            "Equity purchase $/sh": [result.entry_equity / case.shares],
            "Fees": [result.fees],
            "Entry net debt": [result.entry_net_debt],
            "Exit net debt": [result.exit_net_debt],
            "Exit EV": [result.exit_ev],
            "Target IRR": [case.assumptions.lbo.target_irr],
        },
        index=["Base case"],
    )
    table(detail, digits=2)
    warnings_box(result.warnings)


def show_sotp(result, case: Case) -> None:
    section("Sum of the parts", f"Basis: {result.basis} · year {result.year}")
    kpi_row([
        ("EV (pre-discount)", _fmt(result.enterprise_value, "num1")),
        ("EV (after discount)", _fmt(result.enterprise_value_after_discount, "num1")),
        ("Net debt", _fmt(result.net_debt, "num1")),
        ("Equity value", _fmt(result.equity_value, "num1")),
        ("Price $/sh", _fmt(result.price, "price")),
        ("EBITDA gap", _fmt(result.ebitda_gap, "num1")),
    ])
    if not result.by_segment.empty:
        table(result.by_segment, digits=1, caption="Segment allocation (not audited segment history)")
    warnings_box(result.warnings)


def show_bridge(bridge: pd.DataFrame, case: Case) -> None:
    section("Valuation bridge", "Same case, several methods — disagreement is the result, not something to average away")
    mids = bridge["mid"].dropna()
    kpi_row([
        ("Methods", str(len(mids))),
        ("Low mid", _fmt(mids.min(), "price") if not mids.empty else "—"),
        ("High mid", _fmt(mids.max(), "price") if not mids.empty else "—"),
        ("Market", _fmt(case.price, "price")),
        ("Spread", _fmt(mids.max() - mids.min(), "price") if len(mids) else "—"),
    ])
    view = bridge.copy()
    if case.price is not None:
        view["vs market"] = view["mid"] - case.price
    table(view, digits=2, caption="Per-share equity value by method")
    for _, row in bridge.iterrows():
        note(f"<strong>{row['method']}</strong> — {row['note']}")


def show_model_snapshot(case: Case) -> None:
    """One-screen KPI strip across DCF / comps / LBO / SOTP / bridge for notebook 00."""
    from valuation.bridge import valuation_bridge
    from valuation.comps import run_comps
    from valuation.dcf import run_dcf
    from valuation.lbo import run_lbo
    from valuation.statements import Line, audit, forecast_statements, identity_failures
    from valuation.case import TOL

    fc = forecast_statements(case)
    ties = identity_failures(audit(fc.statements), tol=TOL).empty
    dcf = run_dcf(case)
    comps = run_comps(case)
    lbo = run_lbo(case)
    bridge = valuation_bridge(case)

    comps_mid = "—"
    if not comps.implied.empty:
        row = comps.implied.iloc[0]
        comps_mid = _fmt(row["price_mid"], "price")

    sotp_price = "—"
    if case.segments:
        from valuation.sotp import run_sotp

        sotp_price = _fmt(run_sotp(case).price, "price")

    mids = bridge["mid"].dropna()
    section(
        "Model snapshot",
        f"Forecast ties: {'yes' if ties else 'NO'} · years {fc.statements.income_years()[0]}–{fc.statements.income_years()[-1]}",
    )
    kpi_row([
        ("DCF Gordon", _fmt(dcf.gordon_price, "price")),
        ("DCF Exit", _fmt(dcf.exit_price, "price")),
        ("Comps mid", comps_mid),
        ("LBO IRR", _fmt(lbo.irr, "pct") if lbo.irr is not None else "—"),
        ("SOTP", sotp_price),
        ("Bridge span", _fmt(mids.max() - mids.min(), "price") if len(mids) else "—"),
    ])
    last = case.history.income_years()[-1]
    note(
        f"History {last}: revenue {_fmt(case.history.income.loc[Line.REVENUE, last], 'num1')} · "
        f"EBITDA {_fmt(case.history.income.loc[Line.EBITDA, last], 'num1')} · "
        f"Open notebooks 01–06 for full exhibits."
    )
    warnings_box(dcf.warnings[:2] + comps.warnings[:1], title="Watch", limit=3)


def show_statements_headline(case: Case, forecast) -> None:
    last = case.history.income_years()[-1]
    first_f = forecast.statements.income_years()[0]
    last_f = forecast.statements.income_years()[-1]
    from valuation.statements import Line

    section("Three-statement forecast", f"History through {last} · forecast {first_f}–{last_f}")
    kpi_row([
        (f"Revenue {last}", _fmt(case.history.income.loc[Line.REVENUE, last], "num1")),
        (f"Revenue {last_f}", _fmt(forecast.statements.income.loc[Line.REVENUE, last_f], "num1")),
        (f"EBITDA {last}", _fmt(case.history.income.loc[Line.EBITDA, last], "num1")),
        (f"Cash {last}", _fmt(case.history.balance.loc[Line.CASH, last], "num1")),
        (f"Cash {last_f}", _fmt(forecast.statements.balance.loc[Line.CASH, last_f], "num1")),
        (f"Debt {last_f}", _fmt(forecast.statements.balance.loc[Line.DEBT, last_f], "num1")),
    ])
    note(
        "Forecast cash that piles up is not extra value. The DCF discounts unlevered free cash flow once "
        "and subtracts only latest-balance-sheet net debt."
    )
