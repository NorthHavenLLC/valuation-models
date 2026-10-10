"""Interactive research figures (Plotly) — SSRN / arXiv visual language.

Line / bar / pie / heatmap / 3D sensitivity panels share one theme
(``valuation.theme``). Hover and orbit make surfaces and matrices usable as
models, not just static exhibits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from valuation import theme as T
from valuation.case import Case
from valuation.chart_data import _surface_data, _surface_slice, surface_diagnostics
from valuation.statements import Line

SERIES = T.SERIES
PALETTE = T.PALETTE  # re-export for notebooks that used viz.PALETTE via plots


def show(fig: go.Figure) -> go.Figure:
    fig.show(auto_play=False, config={
        "displaylogo": False, "responsive": True, "scrollZoom": False,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "toImageButtonOptions": {"format": "png", "scale": 3},
    })
    return fig


def paper_layout(
    fig: go.Figure,
    *,
    title: str | None = None,
    caption: str | None = None,
    ylabel: str = "",
    height: int = 480,
    showlegend: bool = True,
    y_right: bool = True,
) -> go.Figure:
    """Research figures with a clear title hierarchy, quiet axes and shared trace styling."""
    full_title = title or ""
    if caption:
        cap = f"<span style='font-size:12px;color:{T.MUTE};font-weight:400'>{caption}</span>"
        full_title = f"{full_title}<br>{cap}" if title else cap

    fig.update_layout(
        title=dict(
            text=full_title,
            x=0.035,
            xanchor="left",
            font=dict(size=18, color=T.INK, family=T.FONT_TITLE),
        ),
        paper_bgcolor=T.PAPER,
        plot_bgcolor=T.PLOT,
        font=dict(family=T.FONT_BODY, size=12, color=T.MUTE),
        height=max(height, 500),
        margin=dict(l=64, r=72, t=110 if (title or caption) else 56, b=100),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.20,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=T.INK, family=T.FONT_BODY),
            itemsizing="constant",
        ),
        showlegend=showlegend,
        hovermode="x unified",
        template="none",
        colorway=SERIES,
        bargap=0.30,
        bargroupgap=0.10,
        waterfallgap=0.32,
        uirevision="valuation-figures",
        uniformtext=dict(minsize=10, mode="hide"),
        hoverlabel=dict(
            bgcolor=T.INK,
            font_size=12,
            font_color=T.PAPER,
            font_family=T.FONT_BODY,
            bordercolor=T.RULE,
            align="left",
        ),
        separators=".,",
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        linecolor=T.RULE,
        linewidth=0.8,
        ticks="outside",
        ticklen=0,
        tickcolor=T.RULE,
        tickfont=dict(color=T.MUTE, size=11, family=T.FONT_BODY),
        title_font=dict(color=T.MUTE, size=11, family=T.FONT_BODY),
        automargin=True,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=T.GRID,
        gridwidth=0.8,
        zeroline=False,
        side="right" if y_right else "left",
        linecolor=T.RULE,
        linewidth=0.8,
        ticks="outside",
        ticklen=0,
        tickcolor=T.RULE,
        tickfont=dict(color=T.MUTE, size=11, family=T.FONT_BODY),
        title=dict(text=ylabel, font=dict(color=T.MUTE, size=10, family=T.FONT_BODY)),
        automargin=True,
        tickformat=",.4~g",
        nticks=5,
    )
    groups = {}
    for trace in fig.data:
        if trace.type == "scatter" and trace.stackgroup:
            key = (trace.xaxis, trace.yaxis, trace.stackgroup)
            groups.setdefault(key, []).append(trace)
    for traces in groups.values():
        total = np.sum([np.asarray(t.y, dtype=float) for t in traces], axis=0)
        for trace in traces:
            values = np.asarray(trace.y, dtype=float)
            shares = np.divide(values, total, out=np.full_like(values, np.nan), where=total != 0)
            trace.customdata = np.column_stack([shares, total, values])
            trace.hovertemplate = ("%{x}<br><b>%{customdata[2]:,.1f}</b> · %{customdata[0]:.1%} of net total"
                                   "<br>Net total: %{customdata[1]:,.1f}<extra>%{fullData.name}</extra>")
    # Shared trace treatment leaves data, trace order and axis semantics intact.
    for trace in fig.data:
        if trace.type == "scatter":
            if trace.stackgroup:
                color = trace.fillcolor or T.ACCENT
                trace.update(mode="lines", line=dict(color=T.PAPER, width=0.7),
                             fillcolor=T.rgba(color, 0.84) if color.startswith("#") else color)
            elif trace.mode != "markers" and (trace.mode is None or "lines" in trace.mode):
                trace.line.width = max(trace.line.width or 0, 2.4)
                if trace.x is not None and len(trace.x) <= 18:
                    trace.update(mode="lines+markers", marker=dict(size=5, color=trace.line.color,
                                 line=dict(color=T.PAPER, width=1)))
            if trace.hovertemplate is None:
                trace.hovertemplate = "%{x}<br>%{y:,.2f}<extra>%{fullData.name}</extra>"
        elif trace.type == "bar":
            trace.update(marker_line=dict(color=T.PAPER, width=0.7), cliponaxis=False)
            if trace.hovertemplate is None:
                trace.hovertemplate = ("%{y}<br>%{x:,.2f}" if trace.orientation == "h"
                                       else "%{x}<br>%{y:,.2f}") + "<extra>%{fullData.name}</extra>"
        elif trace.type == "waterfall":
            trace.update(cliponaxis=False)
    seen = set()
    for trace in fig.data:
        if trace.name and trace.showlegend is not False:
            trace.legendgroup = trace.legendgroup or trace.name
            if trace.name in seen:
                trace.showlegend = False
            seen.add(trace.name)
        if trace.type == "bar":
            axis_name = (trace.xaxis or "x") if trace.orientation == "h" else (trace.yaxis or "y")
            key = axis_name[0] + "axis" + axis_name[1:]
            fig.layout[key].rangemode = "tozero"
    return fig


def _forecast_band(fig, years, history_end):
    """Shade whole categorical periods, including a single forecast year."""
    if history_end is None:
        return
    future = [i for i, year in enumerate(years) if int(year) > history_end]
    if not future:
        return
    for col in (1, 2):
        fig.add_vrect(x0=future[0] - 0.5, x1=len(years) - 0.5,
                      fillcolor=T.rgba(T.STEEL, 0.10), line_width=0,
                      layer="below", row=1, col=col,
                      annotation_text="FORECAST", annotation_position="top left",
                      annotation_font=dict(size=9, color=T.MUTE))


# Back-compat alias
desk_layout = paper_layout


def _series_end_labels(data, palette, *, suffix=""):
    """Direct labels for short comparison sets with complete last observations."""
    if data.empty or not 1 <= len(data.columns) <= 5 or not np.isfinite(data.iloc[-1]).all():
        return None
    finite = data.to_numpy()[np.isfinite(data.to_numpy())]
    low, high = float(finite.min()), float(finite.max())
    span = max(high-low, abs(high)*.01, 1e-9)
    values = data.iloc[-1].to_numpy(dtype=float)
    pixels = (values-low)/span*280
    order = np.argsort(pixels)
    adjusted = pixels.copy()
    for previous, current in zip(order, order[1:]):
        adjusted[current] = max(adjusted[current], adjusted[previous]+19)
    adjusted -= float(np.mean(adjusted-pixels))
    return [dict(x=1.015, y=float(value), xref="paper", yref="y", xanchor="left",
                 yshift=float(adjusted[i]-pixels[i]), showarrow=False,
                 text=f"{str(col)} · {value:,.1f}{suffix}",
                 font=dict(size=11, color=palette[i % len(palette)]))
            for i, (col, value) in enumerate(zip(data.columns, values))]


def plot_desk_series(
    frame: pd.DataFrame,
    *,
    title: str | None = None,
    ylabel: str = "",
    y_as_pct: bool = False,
    colors: list[str] | None = None,
) -> go.Figure:
    data = frame.astype(float).copy()
    if y_as_pct:
        data = data * 100.0
    palette = colors or [T.FINANCIAL.get(str(col), SERIES[i % len(SERIES)])
                         for i, col in enumerate(data.columns)]
    fig = go.Figure()
    prior = data.shift(1)
    changes = data - prior
    for i, col in enumerate(data.columns):
        fig.add_trace(
            go.Scatter(
                x=data.index.tolist(),
                y=data[col].tolist(),
                mode="lines",
                name=str(col),
                line=dict(color=palette[i % len(palette)], width=2.0,
                          dash=["solid", "solid", "dash", "dot"][i % 4]),
                connectgaps=False,
                customdata=np.column_stack([data[col], changes[col]]),
                hovertemplate="<b>%{y:,.2f}" + ("%" if y_as_pct else "")
                              + "</b><br>Change from previous observation: %{customdata[1]:+,.2f}"
                              + (" pp" if y_as_pct else "") + "<extra>%{fullData.name}</extra>",
            )
        )
    ylab = f"{ylabel} (%)".replace(" (%) (%)", " (%)") if y_as_pct and ylabel else (ylabel or ("%" if y_as_pct else ""))
    paper_layout(fig, title=title, ylabel=ylab, caption="Hover to compare observations")
    end_labels = _series_end_labels(data, palette, suffix="%" if y_as_pct else "")
    if end_labels is not None:
        fig.update_layout(annotations=end_labels, showlegend=False, margin=dict(r=190, b=55))
        fig.update_yaxes(side="left")
    if y_as_pct:
        fig.update_yaxes(ticksuffix=" %")
    if not y_as_pct and not data.empty and np.isfinite(data.iloc[0]).all() and (data.iloc[0] > 0).all():
        levels = [data[col].tolist() for col in data]
        indexed = [(data[col]/data[col].iloc[0]*100).tolist() for col in data]
        indexed_frame = data.divide(data.iloc[0])*100
        indexed_labels = _series_end_labels(indexed_frame, palette)
        fig.update_layout(updatemenus=[dict(type="buttons", direction="right", x=1, xanchor="right",
            y=1.06, bgcolor=T.SOFT, bordercolor=T.RULE, font=dict(size=10), buttons=[
                dict(label="Levels", method="update", args=[{"y": levels, "hovertemplate":
                    "<b>%{y:,.2f}</b><br>Change: %{customdata[1]:+,.2f}<extra>%{fullData.name}</extra>"},
                    {"yaxis.title.text": ylabel, "yaxis.autorange": True, "annotations": end_labels or []}]),
                dict(label="Indexed · 100", method="update", args=[{"y": indexed, "hovertemplate":
                    "<b>%{y:.1f} index</b><br>Actual: %{customdata[0]:,.2f}<extra>%{fullData.name}</extra>"},
                    {"yaxis.title.text": "First observation = 100", "yaxis.autorange": True, "annotations": indexed_labels or []}])])])
    return show(fig)


def plot_income_stack(statements, unit: str = "", history_end: int | None = None) -> go.Figure:
    years = [str(int(c)) for c in statements.income.columns]
    revenue = statements.income.loc[Line.REVENUE].astype(float)
    cogs = statements.income.loc[Line.COGS].astype(float)
    opex = statements.income.loc[Line.OPEX].astype(float)
    da = statements.income.loc[Line.DA].astype(float)
    ebit = statements.income.loc[Line.EBIT].astype(float)
    ebitda = statements.income.loc[Line.EBITDA].astype(float)
    ni = statements.income.loc[Line.NET_INCOME].astype(float)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Revenue composition", "Earnings"),
        horizontal_spacing=0.10,
    )
    for name, series, color in (
        ("COGS", cogs, T.FINANCIAL["COGS"]),
        ("OpEx", opex, T.FINANCIAL["OpEx"]),
        ("D&A", da, T.FINANCIAL["D&A"]),
        ("EBIT", ebit, T.FINANCIAL["EBIT"]),
    ):
        fig.add_trace(
            go.Scatter(
                x=years, y=series.tolist(), name=name, stackgroup="one",
                mode="none", fillcolor=color, line=dict(width=0),
                hovertemplate="%{y:,.1f}<extra>%{fullData.name}</extra>",
            ),
            row=1, col=1,
        )
    fig.add_trace(
        go.Scatter(x=years, y=revenue.tolist(), name="Revenue",
                   line=dict(color=T.INK, width=2.2),
                   hovertemplate="%{y:,.1f}<extra>Revenue</extra>"),
        row=1, col=1,
    )
    for name, series, color in (
        ("EBIT", ebit, T.FINANCIAL["EBIT"]),
        ("EBITDA", ebitda, T.FINANCIAL["EBITDA"]),
        ("Net income", ni, T.FINANCIAL["Net income"]),
    ):
        fig.add_trace(
            go.Scatter(x=years, y=series.tolist(), name=name,
                       line=dict(color=color, width=2.0),
                       hovertemplate="%{y:,.1f}<extra>%{fullData.name}</extra>"),
            row=1, col=2,
        )
    paper_layout(fig, title="Income statement", ylabel=unit, height=560,
                 caption="Revenue composition and earnings · amounts in " + (unit or "reporting units"))
    earnings_indices = [i for i, trace in enumerate(fig.data) if trace.xaxis == "x2"]
    levels = [list(fig.data[i].y) for i in earnings_indices]
    margins = [(np.asarray(values) / revenue.replace(0, np.nan).to_numpy() * 100).tolist()
               for values in levels]
    fig.update_layout(updatemenus=[dict(
        type="buttons", direction="right", x=1, xanchor="right", y=1.18, showactive=True,
        bgcolor=T.SOFT, bordercolor=T.RULE, font=dict(size=10),
        buttons=[dict(label=label, method="update", args=[
            {"y": values, "hovertemplate": hover},
            {"yaxis2.title.text": axis_title, "yaxis2.ticksuffix": suffix, "yaxis2.autorange": True},
            earnings_indices])
            for label, values, hover, axis_title, suffix in (
                ("Earnings", levels, "%{y:,.1f}<extra>%{fullData.name}</extra>", unit, ""),
                ("Margins", margins, "%{y:.1f}%<extra>%{fullData.name}</extra>", "Share of revenue", "%"))])])
    fig.update_yaxes(zeroline=True, zerolinecolor=T.RULE, row=1, col=2)
    _forecast_band(fig, years, history_end)
    fig.update_annotations(font=dict(family=T.FONT_TITLE, size=11, color=T.MUTE))
    return show(fig)


def plot_balance_composition(statements, unit: str = "", history_end: int | None = None) -> go.Figure:
    years = [str(int(c)) for c in statements.balance.columns]
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Assets", "Funding"),
        horizontal_spacing=0.12,
    )
    for name, key, color in (
        ("Cash", Line.CASH, T.OLIVE),
        ("AR", Line.AR, T.NAVY),
        ("Inventory", Line.INVENTORY, T.AMBER),
        ("PP&E", Line.PPE, T.STEEL),
        ("Other", Line.OTHER_ASSETS, T.SLATE),
    ):
        series = statements.balance.loc[key].astype(float)
        fig.add_trace(
            go.Scatter(x=years, y=series.tolist(), name=name, stackgroup="a",
                       mode="none", fillcolor=color, line=dict(width=0)),
            row=1, col=1,
        )
    for name, key, color in (
        ("Payables", Line.AP, T.AMBER),
        ("Debt", Line.DEBT, T.RUST),
        ("Other liab.", Line.OTHER_LIAB, T.SLATE),
        ("Equity", Line.EQUITY, T.NAVY),
    ):
        series = statements.balance.loc[key].astype(float)
        fig.add_trace(
            go.Scatter(x=years, y=series.tolist(), name=name, stackgroup="f",
                       mode="none", fillcolor=color, line=dict(width=0)),
            row=1, col=2,
        )
    paper_layout(fig, title="Balance sheet composition", ylabel=unit, height=560,
                 caption="Asset allocation and funding sources · signed balances preserved")
    # Percent composition is meaningful only for nonnegative, nonempty totals.
    values = np.asarray([trace.y for trace in fig.data], dtype=float)
    if np.isfinite(values).all() and (values >= 0).all() and (values.sum(axis=0) > 0).all():
        fig.update_layout(updatemenus=[dict(
            type="buttons", direction="right", x=1, xanchor="right", y=1.18,
            bgcolor=T.SOFT, bordercolor=T.RULE, font=dict(size=10),
            buttons=[dict(label=label, method="update", args=[
                {"groupnorm": norm},
                {"yaxis.title.text": axis_title, "yaxis2.title.text": axis_title,
                 "yaxis.ticksuffix": suffix, "yaxis2.ticksuffix": suffix,
                 "yaxis.autorange": True, "yaxis2.autorange": True}])
                for label, norm, axis_title, suffix in (
                    ("Amounts", "", unit, ""), ("Composition", "percent", "Share of total", "%"))])])
    _forecast_band(fig, years, history_end)
    fig.update_annotations(font=dict(family=T.FONT_TITLE, size=11, color=T.MUTE))
    return show(fig)


def plot_cash_bridge(cashflow: pd.DataFrame, unit: str = "") -> go.Figure:
    years = [str(int(c)) for c in cashflow.columns]
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Cash flow by activity", "Cash balance"),
        horizontal_spacing=0.12,
    )
    for name, key, color in (
        ("CFO", Line.CFO, T.OLIVE),
        ("CFI", Line.CFI, T.RUST),
        ("CFF", Line.CFF, T.NAVY),
    ):
        fig.add_trace(
            go.Bar(x=years, y=cashflow.loc[key].astype(float).tolist(), name=name,
                   marker_color=color, marker_line_width=0),
            row=1, col=1,
        )
    open_c = cashflow.loc[Line.OPEN_CASH].astype(float)
    close_c = cashflow.loc[Line.CLOSE_CASH].astype(float)
    net = cashflow.loc[Line.NET_CHANGE].astype(float)
    fig.add_trace(
        go.Bar(x=years, y=net.tolist(), name="Net change",
               marker_color=[T.OLIVE if v >= 0 else T.RUST for v in net], opacity=0.5),
        row=1, col=2,
    )
    fig.add_trace(go.Scatter(x=years, y=open_c.tolist(), name="Opening",
                             line=dict(color=T.SLATE, width=1.8)), row=1, col=2)
    fig.add_trace(go.Scatter(x=years, y=close_c.tolist(), name="Closing",
                             line=dict(color=T.OLIVE, width=2.0)), row=1, col=2)
    paper_layout(fig, title="Cash flow", ylabel=unit, height=520)
    fig.update_layout(barmode="relative")
    fig.update_yaxes(zeroline=True, zerolinecolor=T.RULE)
    fig.update_annotations(font=dict(family=T.FONT_TITLE, size=11, color=T.MUTE))
    return show(fig)


def plot_working_capital(statements, unit: str = "") -> go.Figure:
    years = [str(int(c)) for c in statements.balance.columns]
    ar = statements.balance.loc[Line.AR].astype(float)
    inv = statements.balance.loc[Line.INVENTORY].astype(float)
    ap = statements.balance.loc[Line.AP].astype(float)
    nwc = ar + inv - ap
    revenue = statements.income.loc[Line.REVENUE].reindex(statements.balance.columns).astype(float)
    nwc_days = (nwc / revenue.replace(0, np.nan)) * 365
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Working capital", "Days of revenue"),
        horizontal_spacing=0.12,
    )
    fig.add_trace(go.Bar(x=years, y=ar.tolist(), name="Receivables", marker_color=T.NAVY), row=1, col=1)
    fig.add_trace(go.Bar(x=years, y=inv.tolist(), name="Inventory", marker_color=T.AMBER), row=1, col=1)
    fig.add_trace(go.Bar(x=years, y=(-ap).tolist(), name="Payables (−)", marker_color=T.RUST), row=1, col=1)
    fig.add_trace(go.Scatter(x=years, y=nwc.tolist(), name="Net WC",
                             line=dict(color=T.INK, width=2.0)), row=1, col=1)
    fig.add_trace(
        go.Scatter(x=years, y=nwc_days.tolist(), name="NWC days",
                   line=dict(color=T.NAVY, width=2.0), fill="tozeroy",
                   fillcolor="rgba(15,61,92,0.10)"),
        row=1, col=2,
    )
    paper_layout(fig, title="Working capital", ylabel=unit, height=520)
    fig.update_layout(barmode="relative")
    fig.update_yaxes(title_text="Days of revenue", row=1, col=2)
    fig.update_annotations(font=dict(family=T.FONT_TITLE, size=11, color=T.MUTE))
    return show(fig)


def plot_ufcf_waterfall(schedule: pd.DataFrame, unit: str = "") -> go.Figure:
    labels = [str(i) for i in schedule.index]
    values = schedule["Present value"].astype(float).tolist()
    colors = [T.AMBER if lab == "Terminal value" else T.NAVY for lab in labels]
    fig = go.Figure(
        go.Bar(
            x=labels, y=values, marker_color=colors, marker_line_width=0,
            text=[f"{v:,.0f}" for v in values], textposition="outside",
            textfont=dict(size=10, color=T.MUTE),
            hovertemplate="%{x}<br>%{y:,.1f}<extra></extra>",
            name="PV",
        )
    )
    cumulative = np.cumsum(values)
    fig.add_trace(
        go.Scatter(
            x=labels, y=cumulative.tolist(), name="Cumulative PV",
            mode="lines+markers",
            line=dict(color=T.INK, width=1.8),
            marker=dict(size=6, color=T.INK),
        )
    )
    paper_layout(fig, title="Unlevered FCF — present value by period", ylabel=unit, height=460,
                 caption="Terminal bar uses the final-year discount factor")
    return show(fig)


def plot_dcf_pv_split(result) -> go.Figure:
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=(
            f"Gordon · ${result.gordon_price:,.2f}/sh · TV {result.gordon_tv_share:.0%}",
            f"Exit multiple · ${result.exit_price:,.2f}/sh · TV {result.exit_tv_share:.0%}",
        ),
        horizontal_spacing=0.12,
    )
    for col, schedule in ((1, result.gordon_schedule), (2, result.exit_schedule)):
        explicit = float(schedule.drop(index="Terminal value")["Present value"].sum())
        terminal = float(schedule.loc["Terminal value", "Present value"])
        fig.add_trace(
            go.Bar(
                x=["Explicit UFCF", "Terminal"],
                y=[explicit, terminal],
                marker_color=[T.NAVY, T.AMBER],
                marker_line_width=0,
                text=[f"{explicit:,.0f}", f"{terminal:,.0f}"],
                textposition="outside",
                showlegend=False,
                hovertemplate="%{x}: %{y:,.1f}<extra></extra>",
            ),
            row=1, col=col,
        )
    paper_layout(fig, title="Enterprise value composition", ylabel="Present value", height=420, showlegend=False)
    fig.update_annotations(font=dict(family=T.FONT_TITLE, size=11, color=T.INK))
    return show(fig)


def plot_composition(
    labels,
    values,
    *,
    title: str = "Composition",
    hole: float = 0.62,
) -> go.Figure:
    """Research-style donut (preferred over raw pie for print clarity)."""
    vals = [max(0.0, float(v)) for v in values]
    labs = [str(x) for x in labels]
    fig = go.Figure(
        go.Pie(
            labels=labs,
            values=vals,
            hole=hole,
            sort=False,
            direction="clockwise",
            marker=dict(colors=[SERIES[i % len(SERIES)] for i in range(len(labs))], line=dict(color=T.PAPER, width=2)),
            textinfo="label+percent",
            textposition="outside",
            automargin=True,
            textfont=dict(size=12, color=T.INK, family=T.FONT_BODY),
            hovertemplate="%{label}<br>%{value:,.1f} (%{percent})<extra></extra>",
        )
    )
    paper_layout(fig, title=title, height=440, showlegend=False, y_right=False,
                 caption="Shares of the illustrated allocation")
    if hole >= 0.4:
        fig.add_annotation(x=0.5, y=0.5, xref="paper", yref="paper",
                           text=f"<b>{sum(vals):,.0f}</b><br><span style='font-size:11px'>TOTAL</span>",
                           showarrow=False, font=dict(size=23, color=T.INK))
    fig.update_layout(margin=dict(l=70, r=70, t=100, b=50))
    return show(fig)


def plot_football_field(bridge: pd.DataFrame, market_price: float | None = None) -> go.Figure:
    plot = bridge.dropna(subset=["mid"]).reset_index(drop=True)
    fig = go.Figure()
    for i, row in plot.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["low"], row["high"]], y=[i, i],
                mode="lines+markers",
                line=dict(color=T.NAVY, width=7),
                marker=dict(size=8, color=T.NAVY),
                showlegend=False,
                hovertemplate=f"{row['method']}<br>%{{x:.2f}}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[row["mid"]], y=[i], mode="markers",
                marker=dict(size=10, color=T.INK, symbol="diamond"),
                showlegend=False,
                hovertemplate=f"Mid %{{x:.2f}}<extra>{row['method']}</extra>",
            )
        )
    if market_price is not None:
        fig.add_vline(
            x=market_price, line_dash="dash", line_color=T.RUST, line_width=1.5,
            annotation_text=f"Market {market_price:.2f}",
            annotation_font=dict(color=T.RUST, size=11, family=T.FONT_BODY),
        )
    fig.update_yaxes(
        tickmode="array", tickvals=list(range(len(plot))),
        ticktext=plot["method"].tolist(), side="left",
    )
    paper_layout(
        fig, title="Valuation bridge", height=max(380, 52 * len(plot) + 120),
        y_right=False, showlegend=False,
        caption="Range = method low–high; diamond = mid",
    )
    fig.update_yaxes(side="left", showgrid=False)
    fig.update_xaxes(title_text="Equity value per share", showgrid=True, gridcolor=T.GRID)
    return show(fig)


def plot_method_bars(bridge: pd.DataFrame, market_price: float | None = None) -> go.Figure:
    plot = bridge.dropna(subset=["mid"]).copy().iloc[::-1]
    colors = [T.RUST if m == "Market price" else T.NAVY for m in plot["method"]]
    mid = plot["mid"].to_numpy(dtype=float)
    lows = plot["low"].to_numpy(dtype=float)
    highs = plot["high"].to_numpy(dtype=float)
    upside = mid/market_price - 1 if market_price is not None and market_price > 0 else np.full_like(mid, np.nan)
    fig = go.Figure(
        go.Bar(
            x=plot["mid"], y=plot["method"], orientation="h",
            marker_color=colors, marker_line_width=0,
            error_x=dict(type="data", symmetric=False, array=np.maximum(0, highs-mid),
                         arrayminus=np.maximum(0, mid-lows), color=T.INK, thickness=1.2, width=5),
            customdata=np.column_stack([lows, highs, upside]),
            text=[f"{v:,.2f}" for v in plot["mid"]],
            textposition="outside",
            textfont=dict(size=11, color=T.MUTE),
            hovertemplate="<b>%{y}</b><br>Mid: %{x:.2f}<br>Range: %{customdata[0]:.2f}–%{customdata[1]:.2f}"
                          + ("<br>Vs market: %{customdata[2]:+.1%}" if market_price is not None and market_price > 0 else "")
                          + "<extra></extra>",
        )
    )
    if market_price is not None:
        fig.add_vline(x=market_price, line_dash="dash", line_color=T.RUST, line_width=1.5)
    paper_layout(
        fig, title="Valuation estimates and ranges", height=max(360, 44 * len(plot) + 110),
        y_right=False, showlegend=False,
        caption="Bars show mid estimates · whiskers show method ranges · dashed line marks market",
    )
    fig.update_yaxes(side="left", showgrid=False)
    fig.update_xaxes(title_text="Mid equity value per share", showgrid=True, gridcolor=T.GRID)
    return show(fig)


def plot_comps_dashboard(comps_result, case: Case) -> go.Figure:
    peers = comps_result.peers
    if peers.empty:
        fig = go.Figure()
        paper_layout(fig, title="Trading comps — no peers loaded")
        return show(fig)

    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{}, {}], [{"colspan": 2}, None]],
        subplot_titles=("Peer EV/EBITDA", "Peer EV/Sales", "Implied equity value range"),
        vertical_spacing=0.14, horizontal_spacing=0.12,
        row_heights=[0.48, 0.52],
    )

    def _hbar(col_key: str, subject_val: float, row: int, col: int) -> None:
        series = peers[col_key].astype(float).sort_values()
        names = peers.loc[series.index, "name"].astype(str)
        fig.add_trace(
            go.Bar(
                x=series.tolist(), y=names.tolist(), orientation="h",
                marker_color=T.NAVY, marker_line_width=0, showlegend=False,
                texttemplate="%{x:.1f}×", textposition="outside",
                hovertemplate="%{y}: %{x:.1f}x<extra></extra>",
            ),
            row=row, col=col,
        )
        if np.isfinite(subject_val):
            fig.add_vline(x=subject_val, line_dash="dash", line_color=T.RUST, row=row, col=col)
        fig.add_vline(x=float(series.median()), line_dash="dot", line_color=T.AMBER, row=row, col=col)

    _hbar("ev_ebitda", float(comps_result.subject.loc[0, "ev_ebitda"]), 1, 1)
    _hbar("ev_sales", float(comps_result.subject.loc[0, "ev_sales"]), 1, 2)

    implied = comps_result.implied.reset_index(drop=True)
    for i, row in implied.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["price_low"], row["price_high"]], y=[i, i],
                mode="lines+markers", line=dict(color=T.NAVY, width=7),
                marker=dict(size=8, color=T.NAVY), showlegend=False,
            ),
            row=2, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=[row["price_mid"]], y=[i], mode="markers",
                marker=dict(size=10, color=T.INK, symbol="diamond"), showlegend=False,
            ),
            row=2, col=1,
        )
    fig.update_yaxes(
        tickmode="array", tickvals=list(range(len(implied))),
        ticktext=implied["method"].tolist(), row=2, col=1, side="left",
    )
    if case.price is not None:
        fig.add_vline(x=case.price, line_dash="dash", line_color=T.RUST, row=2, col=1)

    paper_layout(fig, title="Trading comps", height=max(660, 26*len(peers)+410), showlegend=False,
                 caption="Dashed = subject; dotted = peer median")
    fig.update_annotations(font=dict(family=T.FONT_TITLE, size=11, color=T.MUTE))
    for r, c in ((1, 1), (1, 2)):
        fig.update_yaxes(side="left", showgrid=False, row=r, col=c)
        fig.update_xaxes(showgrid=True, gridcolor=T.GRID, row=r, col=c)
    fig.update_xaxes(title_text="Implied $/sh", showgrid=True, gridcolor=T.GRID, row=2, col=1)
    return show(fig)


def plot_debt_stack(schedule: pd.DataFrame, unit: str = "") -> go.Figure:
    years = schedule["year"].astype(str).tolist()
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Debt composition", "Debt service and earnings"),
        horizontal_spacing=0.12,
    )
    for name, col, color in (
        ("Revolver", "revolver", T.AMBER),
        ("Term", "term", T.NAVY),
        ("Notes", "notes", T.SLATE),
    ):
        fig.add_trace(
            go.Scatter(x=years, y=schedule[col].tolist(), name=name, stackgroup="debt",
                       mode="none", fillcolor=color, line=dict(width=0)),
            row=1, col=1,
        )
    fig.add_trace(go.Scatter(x=years, y=schedule["cash"].tolist(), name="Cash",
                             line=dict(color=T.INK, width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=years, y=schedule["net_debt"].tolist(), name="Net debt",
                             line=dict(color=T.RUST, width=1.8, dash="dash")), row=1, col=1)
    hold = schedule[schedule["phase"] == "hold"]
    if not hold.empty:
        hy = hold["year"].astype(str).tolist()
        fig.add_trace(go.Bar(x=hy, y=hold["mandatory"].tolist(), name="Mandatory",
                             marker_color=T.RUST), row=1, col=2)
        fig.add_trace(go.Bar(x=hy, y=hold["sweep"].tolist(), name="Sweep",
                             marker_color=T.OLIVE), row=1, col=2)
        fig.add_trace(go.Scatter(x=hy, y=hold["interest"].tolist(), name="Interest",
                                 line=dict(color=T.INK, width=1.8)), row=1, col=2)
        fig.add_trace(go.Scatter(x=hy, y=hold["ebitda"].tolist(), name="EBITDA",
                                 line=dict(color=T.NAVY, width=1.8, dash="dot")), row=1, col=2)
    paper_layout(fig, title="LBO debt dynamics", ylabel=unit, height=560)
    fig.update_layout(barmode="relative")
    fig.update_annotations(font=dict(family=T.FONT_TITLE, size=11, color=T.MUTE))
    return show(fig)


def plot_sotp_waterfall(by_segment: pd.DataFrame, net_debt: float, equity: float, unit: str = "") -> go.Figure:
    rows = list(by_segment.to_dict(orient="records"))
    labels = [r["segment"] for r in rows] + ["Net debt", "Equity value"]
    values = [float(r["enterprise_value"]) for r in rows] + [-float(net_debt), float(equity)]
    # Waterfall via measure
    measures = []
    texts = []
    for lab, val in zip(labels, values):
        if lab == "Equity value":
            measures.append("total")
        else:
            measures.append("relative")
        texts.append(f"{val:,.0f}")
    fig = go.Figure(
        go.Waterfall(
            x=labels, y=values, measure=measures,
            text=texts, textposition="outside",
            connector={"line": {"color": T.RULE, "width": 1}},
            increasing={"marker": {"color": T.NAVY}},
            decreasing={"marker": {"color": T.RUST}},
            totals={"marker": {"color": T.OLIVE}},
            hovertemplate="%{x}<br>%{y:,.1f}<extra></extra>",
        )
    )
    paper_layout(fig, title="Sum of the parts → equity value", ylabel=unit, height=480,
                 showlegend=False, caption="Illustrative segment allocation")
    return show(fig)


# ---------------------------------------------------------------------------
# Interactive heatmaps + 3D sensitivity panels
# ---------------------------------------------------------------------------


def _heatmap_z(display: pd.DataFrame, fmt: str) -> tuple[list, list[list], list[list[str]]]:
    z = display.values.astype(float)
    text = []
    for i in range(z.shape[0]):
        row = []
        for j in range(z.shape[1]):
            v = z[i, j]
            row.append("—" if not np.isfinite(v) else fmt.format(v))
        text.append(row)
    return list(display.columns.astype(str)), z.tolist(), text


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
) -> go.Figure:
    data = frame.astype(float)
    base_value = None
    if base_row is not None and base_col is not None and base_row in data.index and base_col in data.columns:
        base_value = float(data.loc[base_row, base_col])
    display = data - base_value if (delta and base_value is not None and np.isfinite(base_value)) else data.copy()
    if delta and base_value is not None:
        title = f"{title} (Δ vs base {fmt.format(base_value)})"

    finite = display.values[np.isfinite(display.values)]
    if finite.size == 0:
        fig = go.Figure()
        paper_layout(fig, title=title)
        return show(fig)

    xlabels, z, text = _heatmap_z(display, fmt)
    ylabels = list(display.index.astype(str))
    scale = T.SCALE_DIV if delta else T.SCALE_SEQ
    zmin = zmax = None
    if delta:
        limit = max(abs(finite.min()), abs(finite.max()), 1e-9)
        zmin, zmax = -limit, limit

    fig = go.Figure(
        go.Heatmap(
            z=z, x=xlabels, y=ylabels,
            text=text, texttemplate="%{text}" if display.size <= 180 else "",
            textfont=dict(size=11, family=T.FONT_BODY),
            colorscale=scale,
            zmid=0.0 if delta else None,
            zmin=zmin, zmax=zmax,
            colorbar=dict(
                title=dict(text=cbar_label or ("Δ" if delta else ""), font=dict(size=11, color=T.MUTE)),
                thickness=10, len=0.85, outlinewidth=0,
                tickfont=dict(size=10, color=T.MUTE),
            ),
            hovertemplate="%{y} × %{x}<br>%{z:.3f}<extra></extra>",
            xgap=1, ygap=1,
            hoverongaps=False,
        )
    )
    # Base-case outline via scatter box
    if base_row in display.index and base_col in display.columns:
        bi = list(display.index.astype(str)).index(str(base_row))
        bj = list(display.columns.astype(str)).index(str(base_col))
        fig.add_shape(
            type="rect",
            x0=bj - 0.5, x1=bj + 0.5, y0=bi - 0.5, y1=bi + 0.5,
            line=dict(color=T.RUST, width=2.5),
            xref="x", yref="y",
        )
        fig.add_annotation(
            x=bj, y=bi, text="base", showarrow=False,
            font=dict(size=9, color=T.RUST, family=T.FONT_BODY),
            yshift=18,
        )

    paper_layout(
        fig, title=title, height=max(420, 36 * len(ylabels) + 160),
        y_right=False, showlegend=False,
        caption=f"min {np.nanmin(display.values):.2f} · median {np.nanmedian(display.values):.2f} · max {np.nanmax(display.values):.2f}",
    )
    fig.update_yaxes(autorange="reversed", side="left", showgrid=False)
    fig.update_xaxes(showgrid=False, tickangle=0)
    return show(fig)


def plot_sensitivity_pair(
    frame: pd.DataFrame,
    title: str,
    cbar_label: str = "",
    *,
    base_row: str | None = None,
    base_col: str | None = None,
    fmt: str = "{:.1f}",
) -> go.Figure:
    data = frame.astype(float)
    base_value = None
    if base_row in data.index and base_col in data.columns:
        base_value = float(data.loc[base_row, base_col])

    level = data
    delta = (data - base_value) if base_value is not None else data * np.nan

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Level", "Change versus base"),
        horizontal_spacing=0.10,
    )
    for col_i, (display, scale, mid) in enumerate(
        ((level, T.SCALE_SEQ, None), (delta, T.SCALE_DIV, 0.0)), start=1
    ):
        finite = display.values[np.isfinite(display.values)]
        zmin = zmax = None
        if mid is not None and finite.size:
            limit = max(abs(finite.min()), abs(finite.max()), 1e-9)
            zmin, zmax = -limit, limit
        xlabels, z, text = _heatmap_z(display, fmt)
        fig.add_trace(
            go.Heatmap(
                z=z, x=xlabels, y=list(display.index.astype(str)),
                text=text, texttemplate="%{text}" if display.size <= 180 else "",
                textfont=dict(size=10, family=T.FONT_BODY),
                colorscale=scale, zmid=mid, zmin=zmin, zmax=zmax,
                colorbar=dict(title=cbar_label if col_i == 1 else f"Δ {cbar_label}",
                              thickness=10, len=0.75, outlinewidth=0, x=0.45 if col_i == 1 else 1.0),
                hovertemplate="%{y} × %{x}<br>%{z:.3f}<extra></extra>",
                xgap=1, ygap=1,
                hoverongaps=False,
                showscale=True,
            ),
            row=1, col=col_i,
        )
        if base_row in display.index and base_col in display.columns:
            bi = list(display.index.astype(str)).index(str(base_row))
            bj = list(display.columns.astype(str)).index(str(base_col))
            fig.add_shape(
                type="rect",
                x0=bj - 0.5, x1=bj + 0.5, y0=bi - 0.5, y1=bi + 0.5,
                line=dict(color=T.RUST, width=2.2),
                row=1, col=col_i,
            )

    paper_layout(fig, title=title, height=max(440, 34 * len(data) + 180),
                 y_right=False, showlegend=False,
                 caption="Rust outline marks the base-case cell — hover any cell for the exact value")
    fig.update_annotations(font=dict(family=T.FONT_TITLE, size=11, color=T.MUTE))
    for c in (1, 2):
        fig.update_yaxes(autorange="reversed", side="left", showgrid=False, row=1, col=c)
        fig.update_xaxes(showgrid=False, tickangle=0, row=1, col=c)
    return show(fig)


def _surface_explorer(fig, x, y, z, *, mx, my, reference, reference_label,
                      xlabel, ylabel, zlabel, scale, low, high):
    """Add portable Plotly controls; no widget server or notebook callbacks required."""
    diagnostics = surface_diagnostics(x, y, z, reference)
    hover = (f"{xlabel}: %{{x:.3f}}<br>{ylabel}: %{{y:.3f}}<br>"
             f"<b>{zlabel}: %{{z:,.2f}}</b>"
             + (f"<br>Δ vs {reference_label}: %{{customdata[0]:+,.2f}}" if reference is not None else "")
             + f"<br>Local slope / unit of {xlabel}: %{{customdata[1]:+,.2f}}"
             + f"<br>Local slope / unit of {ylabel}: %{{customdata[2]:+,.2f}}<extra></extra>")
    fig.data[0].update(customdata=diagnostics, hovertemplate=hover, showscale=True,
                       colorbar=dict(title=dict(text=zlabel, side="right"), x=.46, y=.77,
                                     len=.46, thickness=9, outlinewidth=0, tickformat=",.3~g"))
    # The map always shows value, so color changes never move the underlying geometry.
    map_trace = next(t for t in fig.data if t.type == "contour")
    map_trace.update(customdata=diagnostics, hovertemplate=hover)
    options = [("Value", z, scale, low, high, zlabel)]
    for label, data, units in (
        ("Δ vs reference", diagnostics[:, :, 0], f"Δ {zlabel}"),
        ("X sensitivity", diagnostics[:, :, 1], "Δ output / unit X"),
        ("Y sensitivity", diagnostics[:, :, 2], "Δ output / unit Y"),
    ):
        finite = data[np.isfinite(data)]
        if not finite.size:
            continue
        limit = max(float(np.max(np.abs(finite))), 1e-9)
        options.append((label, data, T.SCALE_DIV, -limit, limit, units))
    menus = list(fig.layout.updatemenus)
    menus.append(dict(type="dropdown", direction="down", x=1, xanchor="right", y=1.13,
                      yanchor="bottom", bgcolor=T.SOFT, bordercolor=T.RULE, font=dict(size=10),
                      buttons=[dict(label=label, method="restyle", args=[
                          {"surfacecolor": [values], "colorscale": [colors], "cmin": lo, "cmax": hi,
                           "colorbar.title.text": units}, [0]])
                          for label, values, colors, lo, hi, units in options]))

    if reference is not None and low <= reference <= high:
        # A muted reference plane shows where modeled values clear the benchmark.
        plane_index = len(fig.data)
        fig.add_trace(go.Surface(x=[x.min(), x.max()], y=[y.min(), y.max()],
                      z=np.full((2, 2), reference), opacity=.13, showscale=False,
                      colorscale=[[0, T.NEG], [1, T.NEG]], name=reference_label,
                      hoverinfo="skip", visible="legendonly", showlegend=True), row=1, col=1)
        if low < reference < high:
            fig.add_trace(go.Contour(x=x[0], y=y[:, 0], z=z,
                          contours=dict(start=reference, end=reference, size=1, coloring="none",
                                        showlabels=True, labelfont=dict(color=T.NEG, size=11)),
                          line=dict(color=T.NEG, width=2), showscale=False,
                          hoverinfo="skip", showlegend=False, connectgaps=False), row=1, col=2)
        menus.append(dict(type="buttons", x=.53, y=1.13, xanchor="left", yanchor="bottom",
                          bgcolor=T.SOFT, bordercolor=T.RULE, font=dict(size=10), showactive=False,
                          buttons=[dict(label="Reference plane", method="restyle",
                              args=[{"visible": True}, [plane_index]],
                              args2=[{"visible": "legendonly"}, [plane_index]])]))

    frames, sliders = [], []
    for col, fixed_axis, initial, varying, fixed_label, color in (
        (1, y[:, 0], my, xlabel, ylabel, T.ACCENT),
        (2, x[0], mx, ylabel, xlabel, T.WARM),
    ):
        coords = x[0] if col == 1 else y[:, 0]
        values = z if col == 1 else z.T
        # Two explicit alternate assumptions provide context without suggesting a confidence interval.
        for fraction in (.25, .75):
            fixed = float(fixed_axis[0] + np.ptp(fixed_axis)*fraction)
            fig.add_trace(go.Scatter(x=coords, y=_surface_slice(fixed_axis, values, fixed),
                          mode="lines", line=dict(color=T.rgba(color, .40), width=1.3, dash="dot"),
                          showlegend=False, name=f"Comparison: {fixed_label} = {fixed:.2f}",
                          hovertemplate=f"{varying}: %{{x:.2f}}<br>{zlabel}: %{{y:,.2f}}"
                                        f"<extra>{fixed_label} = {fixed:.2f}</extra>"), row=2, col=col)
        curve_index = next(i for i, trace in enumerate(fig.data)
                           if trace.meta == dict(role="slice-2d", axis=col))
        surface_index = next(i for i, trace in enumerate(fig.data)
                             if trace.meta == dict(role="slice-3d", axis=col))
        crosshair_index = len(fig.data)
        cross_x = [float(x.min()), float(x.max())] if col == 1 else [initial, initial]
        cross_y = [initial, initial] if col == 1 else [float(y.min()), float(y.max())]
        fig.add_trace(go.Scatter(x=cross_x, y=cross_y, mode="lines",
                      line=dict(color=color, width=1.5), showlegend=False, hoverinfo="skip"), row=1, col=2)
        positions = np.unique(np.r_[np.linspace(fixed_axis[0], fixed_axis[-1], 13), initial])
        steps = []
        for index, fixed in enumerate(positions):
            sliced = _surface_slice(fixed_axis, values, fixed)
            name = f"{fixed_label} = {fixed:.2f}"
            frame_name = f"slice-{col}-{index}"
            frames.append(go.Frame(name=frame_name, traces=[curve_index, surface_index, crosshair_index], data=[
                go.Scatter(x=coords, y=sliced, name=name,
                           hovertemplate=f"{varying}: %{{x:.2f}}<br>{zlabel}: %{{y:,.2f}}<extra>{name}</extra>"),
                go.Scatter3d(x=coords if col == 1 else np.full_like(coords, fixed),
                             y=np.full_like(coords, fixed) if col == 1 else coords, z=sliced),
                go.Scatter(x=[float(x.min()), float(x.max())] if col == 1 else [fixed, fixed],
                           y=[fixed, fixed] if col == 1 else [float(y.min()), float(y.max())]),
            ]))
            steps.append(dict(label=f"{fixed:.2f}", method="animate", args=[[frame_name],
                              {"mode": "immediate", "frame": {"duration": 0, "redraw": True},
                               "transition": {"duration": 0}}]))
        sliders.append(dict(active=int(np.argmin(abs(positions-initial))), steps=steps,
                            x=0 if col == 1 else .61, len=.39, y=-.13, xanchor="left", yanchor="top",
                            pad=dict(t=35, b=10), ticklen=3, font=dict(size=9, color=T.MUTE),
                            currentvalue=dict(prefix=f"Hold {fixed_label}: ", font=dict(size=11, color=color)),
                            bgcolor=T.RULE, activebgcolor=color, borderwidth=0))
    fig.frames = frames
    valid = int(np.isfinite(z).sum())
    detail = f"{valid:,} / {z.size:,} valid scenarios · dotted curves: 25% and 75% of the other input’s range"
    if reference is not None:
        cleared = int(np.sum(z >= reference))
        detail += f"<br>{cleared:,} sampled values ≥ {reference_label} ({reference:,.2f}) · grid counts are not probabilities"
    if reference is not None and not low <= reference <= high:
        detail += "<br>Benchmark is outside the displayed output range; no intersection contour or plane."
    fig.add_annotation(x=0, y=-.34, xref="paper", yref="paper", xanchor="left", yanchor="top",
                       text=detail, showarrow=False, align="left", font=dict(size=11, color=T.MUTE))
    fig.update_layout(updatemenus=menus, sliders=sliders, height=1120,
                      margin=dict(l=70, r=100, t=155, b=260), legend=dict(y=-.045),
                      meta=dict(surface_explorer=True, reference=reference, reference_label=reference_label,
                                valid_scenarios=valid, total_scenarios=int(z.size)))
    return fig


def plot_surface_panel(
    xx: np.ndarray, yy: np.ndarray, zz: np.ndarray, *,
    xlabel: str, ylabel: str, zlabel: str, title: str,
    x_as_pct: bool = False, y_as_pct: bool = False,
    mark: tuple[float, float, float] | None = None, cmap=None,
    reference: float | None = None, reference_label: str = "Benchmark",
) -> go.Figure:
    """Four linked views of the supplied model grid, with independent slice axes."""
    xx, yy, zz = _surface_data(xx, yy, zz)
    x = xx * 100 if x_as_pct else xx
    y = yy * 100 if y_as_pct else yy
    finite = zz[np.isfinite(zz)]
    if not finite.size:
        fig = paper_layout(go.Figure(), title=title, showlegend=False)
        fig.add_annotation(text="No valid model scenarios in this range", x=0.5, y=0.5,
                           xref="paper", yref="paper", showarrow=False)
        return show(fig)
    low, high = float(finite.min()), float(finite.max())
    span = max(high - low, max(abs(low), 1) * 0.01)
    floor = low - span * 0.12
    scale = cmap if isinstance(cmap, (str, list, tuple)) else T.SCALE_SURFACE
    valid_mark = mark is not None and np.isfinite(mark).all()
    mx = (mark[0] * (100 if x_as_pct else 1)) if valid_mark else float(np.median(x[0]))
    my = (mark[1] * (100 if y_as_pct else 1)) if valid_mark else float(np.median(y[:, 0]))
    in_range = x.min() <= mx <= x.max() and y.min() <= my <= y.max()
    outside_note = ""
    if not in_range:
        valid_mark = False
        mx, my = float(np.median(x[0])), float(np.median(y[:, 0]))
        outside_note = " · base inputs outside displayed range"
    sx = _surface_slice(y[:, 0], zz, my)
    sy = _surface_slice(x[0], zz.T, mx)
    slice_label = "base inputs" if valid_mark else "midpoint inputs"
    fig = make_subplots(
        rows=2, cols=2, specs=[[{"type": "scene"}, {"type": "xy"}],
                               [{"type": "xy"}, {"type": "xy"}]],
        column_widths=[0.55, 0.45], row_heights=[0.67, 0.33],
        horizontal_spacing=0.12, vertical_spacing=0.18,
        subplot_titles=("01  /  MODEL SURFACE", "02  /  ISO-VALUE MAP",
                        f"03  /  {xlabel} sensitivity", f"04  /  {ylabel} sensitivity"),
    )
    hover = f"{xlabel}: %{{x:.2f}}<br>{ylabel}: %{{y:.2f}}<br><b>{zlabel}: %{{z:,.2f}}</b><extra></extra>"
    fig.add_trace(go.Surface(
        x=x, y=y, z=zz, name="Model surface", colorscale=scale, cmin=low, cmax=high,
        connectgaps=False, showscale=False,
        lighting=dict(ambient=0.65, diffuse=0.8, specular=0.16, roughness=0.85, fresnel=0.1),
        lightposition=dict(x=-100, y=-150, z=250),
        contours=dict(z=dict(show=True, start=low, end=high, size=span/12,
                             usecolormap=True, project_z=True, highlightcolor=T.INK)),
        hovertemplate=hover), row=1, col=1)
    # Restrained wireframe conveys model density without obscuring the surface.
    for axis, indices in ((0, np.linspace(0, zz.shape[0]-1, min(9, zz.shape[0]), dtype=int)),
                          (1, np.linspace(0, zz.shape[1]-1, min(9, zz.shape[1]), dtype=int))):
        wx, wy, wz = [], [], []
        for i in indices:
            selection = (i, slice(None)) if axis == 0 else (slice(None), i)
            wx.extend(x[selection].tolist() + [None])
            wy.extend(y[selection].tolist() + [None])
            wz.extend(zz[selection].tolist() + [None])
        fig.add_trace(go.Scatter3d(x=wx, y=wy, z=wz, mode="lines",
                      line=dict(color="rgba(255,255,255,0.35)", width=1),
                      hoverinfo="skip", showlegend=False, connectgaps=False), row=1, col=1)
    fig.add_trace(go.Contour(
        x=x[0], y=y[:, 0], z=zz, colorscale=scale, zmin=low, zmax=high,
        connectgaps=False, hoverongaps=False, ncontours=14,
        contours=dict(showlabels=True, labelfont=dict(size=10, color=T.INK)),
        line=dict(width=0.6, color=T.rgba(T.INK, 0.4)),
        colorbar=dict(title=dict(text=zlabel, side="right"), thickness=10,
                      len=0.55, y=0.74, x=1.02, outlinewidth=0, tickformat=",.3~g"),
        hovertemplate=hover, showscale=True, name="Iso-value map"), row=1, col=2)
    for coords, values, fixed, varying_label, fixed_label, color, col in (
        (x[0], sx, my, xlabel, ylabel, T.ACCENT, 1),
        (y[:, 0], sy, mx, ylabel, xlabel, T.WARM, 2),
    ):
        name = f"{fixed_label} = {fixed:.2f}"
        fig.add_trace(go.Scatter(x=coords, y=values, mode="lines", name=name,
                      line=dict(color=color, width=2.8), connectgaps=False,
                      meta=dict(role="slice-2d", axis=col),
                      hovertemplate=f"{varying_label}: %{{x:.2f}}<br>{zlabel}: %{{y:,.2f}}<extra>{name}</extra>"),
                      row=2, col=col)
        fig.add_trace(go.Scatter3d(
            x=coords if col == 1 else np.full_like(coords, mx),
            y=np.full_like(coords, my) if col == 1 else coords, z=values,
            mode="lines", line=dict(color=color, width=6), hoverinfo="skip",
            meta=dict(role="slice-3d", axis=col),
            showlegend=False, connectgaps=False), row=1, col=1)
    fig.add_shape(type="line", x0=mx, x1=mx, y0=float(y.min()), y1=float(y.max()),
                  line=dict(color=T.WARM, dash="dash", width=1.3), row=1, col=2)
    fig.add_shape(type="line", x0=float(x.min()), x1=float(x.max()), y0=my, y1=my,
                  line=dict(color=T.ACCENT, dash="dash", width=1.3), row=1, col=2)
    if valid_mark:
        mz = float(mark[2])
        fig.add_trace(go.Scatter3d(x=[mx, mx], y=[my, my], z=[floor, mz],
                      mode="lines", line=dict(color=T.NEG, width=3, dash="dot"),
                      showlegend=False, hoverinfo="skip"), row=1, col=1)
        fig.add_trace(go.Scatter3d(x=[mx], y=[my], z=[mz], mode="markers",
                      name=f"Base case · {mz:,.2f}", marker=dict(size=6, color=T.NEG, symbol="diamond"),
                      hovertemplate=hover), row=1, col=1)
        fig.add_trace(go.Scatter(x=[mx], y=[my], mode="markers",
                      marker=dict(size=11, color=T.NEG, symbol="diamond", line=dict(color=T.PAPER, width=2)),
                      showlegend=False, hovertemplate=f"Base case: {mz:,.2f}<extra></extra>"), row=1, col=2)
        for col, coordinate in ((1, mx), (2, my)):
            fig.add_shape(type="line", x0=0, x1=1, y0=mz, y1=mz,
                          xref=f"x{col+1} domain", yref=f"y{col+1}",
                          line=dict(color=T.NEG, width=1, dash="dot"))
            fig.add_trace(go.Scatter(x=[coordinate], y=[mz], mode="markers",
                          marker=dict(size=7, color=T.NEG), showlegend=False,
                          hovertemplate=f"Base case: {mz:,.2f}<extra></extra>"), row=2, col=col)
    caption = f"{zz.shape[1]} × {zz.shape[0]} scenarios · range {low:,.2f}–{high:,.2f} · slices start at {slice_label}{outside_note}"
    paper_layout(fig, title=title, caption=caption, height=940, y_right=False)
    fig.update_annotations(font=dict(size=11, color=T.MUTE, family=T.FONT_BODY))
    def scene_axis(label):
        return dict(title=dict(text=label, font=dict(size=11)), backgroundcolor=T.SOFT,
                    showbackground=True, gridcolor=T.RULE, zeroline=False,
                    showspikes=False, tickfont=dict(size=10), nticks=5)
    fig.update_layout(
        scene=dict(xaxis=scene_axis(xlabel), yaxis=scene_axis(ylabel),
                   zaxis={**scene_axis(zlabel), "range": [floor, high + span * .06]},
                   camera=dict(eye=dict(x=1.55, y=-1.65, z=1.05), projection=dict(type="orthographic")),
                   aspectmode="manual", aspectratio=dict(x=1.2, y=1, z=.72)),
        hovermode="closest", margin=dict(l=70, r=100, t=155, b=110),
        legend=dict(y=-0.12),
        updatemenus=[dict(type="buttons", direction="right", x=0, y=1.13,
                          xanchor="left", yanchor="bottom", showactive=False,
                          bgcolor=T.SOFT, bordercolor=T.RULE, font=dict(size=10),
                          buttons=[dict(label=label, method="relayout",
                                        args=[{"scene.camera": dict(eye=eye, projection=dict(type="orthographic"))}])
                                   for label, eye in (("Perspective", dict(x=1.55, y=-1.65, z=1.05)),
                                                      ("Top view", dict(x=0, y=0, z=2.5)),
                                                      ("Front view", dict(x=0, y=-2.5, z=.45)))])],
    )
    for row, col, xl, yl in ((1, 2, xlabel, ylabel), (2, 1, xlabel, zlabel), (2, 2, ylabel, zlabel)):
        fig.update_xaxes(title_text=xl, showgrid=True, gridcolor=T.GRID, row=row, col=col)
        fig.update_yaxes(title_text=yl, side="left", row=row, col=col)
    for col in (1, 2):
        fig.update_yaxes(range=[low - .06*span, high + .06*span], row=2, col=col)
    benchmark = reference if reference is not None and np.isfinite(reference) else (float(mark[2]) if valid_mark else None)
    label = reference_label if reference is not None and np.isfinite(reference) else "Base case"
    _surface_explorer(fig, x, y, zz, mx=mx, my=my, reference=benchmark, reference_label=label,
                      xlabel=xlabel, ylabel=ylabel, zlabel=zlabel, scale=scale, low=low, high=high)
    return show(fig)


def plot_sources_uses(sources_uses: pd.DataFrame, unit: str = "") -> go.Figure:
    frame = sources_uses[~sources_uses["item"].str.startswith("Total")]
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.22,
                        subplot_titles=("Sources of capital", "Uses of capital"))
    for col, side, color in ((1, "source", T.POS), (2, "use", T.ACCENT)):
        data = frame[frame["side"] == side].sort_values("amount")
        total = data["amount"].sum()
        shares = data["amount"] / total if total else data["amount"] * np.nan
        fig.add_trace(go.Bar(x=data["amount"], y=data["item"], orientation="h",
                      marker_color=color, texttemplate="%{x:,.0f}", textposition="outside",
                      customdata=shares, hovertemplate="%{y}<br>%{x:,.1f}<br>%{customdata:.1%} of total<extra></extra>"),
                      row=1, col=col)
    paper_layout(fig, title="Transaction funding", caption="Capital raised and deployed · " + unit,
                 height=540, showlegend=False, y_right=False)
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(title_text=unit, showgrid=True, gridcolor=T.GRID)
    return show(fig)


def plot_returns_bridge(bridge: pd.DataFrame, unit: str = "") -> go.Figure:
    wanted = ["Entry firm equity", "EBITDA growth at the exit multiple",
              "Multiple change on entry EBITDA", "Deleveraging", "Exit firm equity"]
    values = bridge.set_index("item").loc[wanted, "amount"].astype(float)
    fig = go.Figure(go.Waterfall(
        x=["Entry equity", "EBITDA growth", "Multiple change", "Deleveraging", "Exit equity"],
        y=values, measure=["absolute", "relative", "relative", "relative", "total"],
        text=[f"{v:,.0f}" for v in values], textposition="outside",
        increasing=dict(marker_color=T.POS), decreasing=dict(marker_color=T.NEG),
        totals=dict(marker_color=T.ACCENT), connector=dict(line=dict(color=T.RULE, width=1)),
        hovertemplate="%{x}<br>%{y:,.1f}<extra></extra>"))
    paper_layout(fig, title="Sources of equity return", ylabel=unit, height=530,
                 showlegend=False, caption="Operating growth, multiple change and debt repayment · fees excluded")
    return show(fig)


def plot_audit_heatmap(gaps: pd.DataFrame) -> go.Figure:
    data = gaps.astype(float)
    finite = data.to_numpy()[np.isfinite(data.to_numpy())]
    limit = max(1.0, float(np.max(np.abs(finite)))) if finite.size else 1.0
    fig = go.Figure(go.Heatmap(
        x=data.columns.astype(str), y=data.index.astype(str), z=data.to_numpy(),
        colorscale=T.SCALE_DIV, zmin=-limit, zmax=limit, zmid=0, xgap=1, ygap=1,
        texttemplate="%{z:,.1f}", hoverongaps=False,
        colorbar=dict(title="Gap", thickness=12, outlinewidth=0),
        hovertemplate="%{y} · %{x}<br>Gap: %{z:,.4f}<extra></extra>"))
    paper_layout(fig, title="Statement reconciliation", height=max(480, len(data)*35+220),
                 caption="Zero indicates a balanced identity · missing observations remain blank",
                 y_right=False, showlegend=False)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return show(fig)
