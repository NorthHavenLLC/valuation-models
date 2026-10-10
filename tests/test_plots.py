import numpy as np
import pandas as pd
import plotly.graph_objects as go

from valuation.dcf import run_dcf
from valuation.plots import (
    exit_price_surface,
    gordon_price_surface,
    lbo_irr_surface,
    nearest_label,
    plot_composition,
    plot_desk_series,
    plot_heatmap,
    plot_sensitivity_pair,
    plot_surface_panel,
    style,
)
from valuation.sample import sample_case


def test_desk_series_renders(monkeypatch):
    import valuation.plots as plots

    monkeypatch.setenv("VALUATION_CHARTS", "matplotlib")
    plots.CHART_ENGINE = "matplotlib"
    style()
    frame = pd.DataFrame(
        {"Tape B": [0.04, 0.05, 0.045], "Tape A": [0.03, 0.035, 0.032], "Tape C": [0.025, 0.028, 0.027]},
        index=[2024, 2025, 2026],
    )
    fig = plot_desk_series(frame, title="Desk UI", ylabel="Rate", y_as_pct=True)
    assert len(fig.axes) >= 1


def test_sensitivity_surfaces_are_finite_near_base_case():
    style()
    case = sample_case()
    xx, yy, zz = gordon_price_surface(case, wacc_steps=6, growth_steps=5)
    assert xx.shape == zz.shape
    assert np.isfinite(zz).sum() >= 10

    xx2, yy2, zz2 = exit_price_surface(case, wacc_steps=6, multiple_steps=5)
    assert np.isfinite(zz2).all()

    xx3, yy3, zz3 = lbo_irr_surface(case, entry_steps=4, exit_steps=4)
    assert np.isfinite(zz3).sum() >= 8


def test_surface_panel_and_heatmap_render_matplotlib(monkeypatch):
    import valuation.plots as plots

    monkeypatch.setenv("VALUATION_CHARTS", "matplotlib")
    plots.CHART_ENGINE = "matplotlib"
    style()
    case = sample_case()
    result = run_dcf(case)
    xx, yy, zz = gordon_price_surface(case, wacc_steps=8, growth_steps=6)
    fig = plot_surface_panel(
        xx,
        yy,
        zz,
        xlabel="WACC (%)",
        ylabel="g (%)",
        zlabel="Price",
        title="test",
        x_as_pct=True,
        y_as_pct=True,
        mark=(result.wacc, case.assumptions.terminal_growth, result.gordon_price),
    )
    assert len(fig.axes) >= 2

    row = nearest_label(result.gordon_sensitivity.index, result.wacc, as_pct=True)
    col = nearest_label(result.gordon_sensitivity.columns, case.assumptions.terminal_growth, as_pct=True)
    assert row in result.gordon_sensitivity.index
    assert col in result.gordon_sensitivity.columns
    fig2 = plot_sensitivity_pair(
        result.gordon_sensitivity,
        "Gordon",
        "$",
        base_row=row,
        base_col=col,
    )
    assert len(fig2.axes) >= 2
    fig3 = plot_heatmap(result.gordon_sensitivity, "Gordon", "$", base_row=row, base_col=col, delta=True)
    assert fig3 is not None


def test_plotly_surface_heatmap_and_composition(monkeypatch):
    import valuation.plotly_charts as pc
    import valuation.plots as plots
    from valuation.plots import gordon_surface_mark

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    plots.CHART_ENGINE = "plotly"
    style()
    case = sample_case()
    result = run_dcf(case)
    wacc, g, price, _ = gordon_surface_mark(case)
    xx, yy, zz = gordon_price_surface(case, wacc_steps=16, growth_steps=16)
    assert xx.shape == (16, 16)
    assert np.isfinite(zz).sum() >= 100
    # Classic shape: higher WACC → lower price at fixed g
    mid_g = zz.shape[0] // 2
    finite_row = zz[mid_g, np.isfinite(zz[mid_g])]
    assert finite_row[0] > finite_row[-1]

    fig = plot_surface_panel(
        xx, yy, zz,
        xlabel="WACC (%)", ylabel="g (%)", zlabel="Price",
        title="Gordon surface",
        x_as_pct=True, y_as_pct=True,
        mark=(wacc, g, price),
    )
    assert isinstance(fig, go.Figure)
    assert any(isinstance(t, go.Surface) for t in fig.data)

    row = nearest_label(result.gordon_sensitivity.index, result.wacc, as_pct=True)
    col = nearest_label(result.gordon_sensitivity.columns, case.assumptions.terminal_growth, as_pct=True)
    heat = plot_heatmap(result.gordon_sensitivity, "Gordon", "$", base_row=row, base_col=col, delta=True)
    assert isinstance(heat, go.Figure)
    assert any(isinstance(t, go.Heatmap) for t in heat.data)

    pair = plot_sensitivity_pair(result.gordon_sensitivity, "Gordon", "$", base_row=row, base_col=col)
    assert isinstance(pair, go.Figure)
    assert sum(isinstance(t, go.Heatmap) for t in pair.data) >= 2

    pie = plot_composition(["A", "B"], [60, 40], title="Mix")
    assert isinstance(pie, go.Figure)
    assert any(isinstance(t, go.Pie) for t in pie.data)


def test_surface_interpolates_exact_inputs_on_independent_axes(monkeypatch):
    import valuation.plotly_charts as pc

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    x, y = np.meshgrid([1., 2., 3.], [10., 20., 30.])
    z = 2*x + 3*y
    fig = pc.plot_surface_panel(x, y, z, xlabel="Discount rate", ylabel="Exit multiple",
                               zlabel="Value", title="Surface", mark=(1.5, 15., 48.))
    slices = [t for t in fig.data if t.type == "scatter" and t.mode == "lines+markers"]
    assert len(slices) == 2
    np.testing.assert_allclose(slices[0].y, 2*x[0] + 45)
    np.testing.assert_allclose(slices[1].y, 3 + 3*y[:, 0])
    assert slices[0].xaxis != slices[1].xaxis
    assert fig.layout.xaxis2.title.text == "Discount rate"
    assert fig.layout.xaxis3.title.text == "Exit multiple"
    assert all(s.xref == "x" and s.yref == "y" for s in fig.layout.shapes[:2])
    assert fig.layout.yaxis2.range == fig.layout.yaxis3.range


def test_surface_keeps_invalid_regions_and_handles_flat_and_empty_grids(monkeypatch):
    import pytest
    import valuation.plotly_charts as pc

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    x, y = np.meshgrid([1., 2., 3.], [1., 2., 3.])
    z = np.ones_like(x)
    z[1, 1] = np.nan
    fig = pc.plot_surface_panel(x, y, z, xlabel="X", ylabel="Y", zlabel="Z", title="Flat")
    surface = next(t for t in fig.data if t.type == "surface")
    assert np.isnan(surface.z[1, 1])
    assert surface.connectgaps is False
    assert np.isnan(pc._surface_slice(y[:, 0], z, 1.5)[1])
    empty = pc.plot_surface_panel(x, y, z*np.nan, xlabel="X", ylabel="Y", zlabel="Z", title="Empty")
    assert "No valid" in empty.layout.annotations[0].text
    with pytest.raises(ValueError, match="matching 2D"):
        pc.plot_surface_panel(x, y, z[:1], xlabel="X", ylabel="Y", zlabel="Z", title="Invalid")


def test_income_preserves_losses_and_single_forecast_period(monkeypatch):
    import valuation.plotly_charts as pc
    from valuation.statements import Line

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    case = sample_case()
    statements = case.history
    last = statements.income.columns[-1]
    statements.income.loc[Line.EBIT, last] = -50
    fig = pc.plot_income_stack(statements, "USD m", history_end=int(last)-1)
    ebit = next(t for t in fig.data if t.name == "EBIT")
    assert ebit.y[-1] == -50
    assert ebit.customdata[-1][0] < 0
    assert len(fig.layout.shapes) == 2
    assert all(s.x1 - s.x0 == 1 for s in fig.layout.shapes)


def test_dates_keep_temporal_spacing_and_working_capital_uses_days(monkeypatch):
    import valuation.plotly_charts as pc

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    dates = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-08-01"])
    frame = pd.DataFrame({"Rate": [.02, .03, .04]}, index=dates)
    fig = pc.plot_desk_series(frame, y_as_pct=True)
    assert list(fig.data[0].x) == list(dates)
    np.testing.assert_allclose(fig.data[0].y, [2, 3, 4])
    wc = pc.plot_working_capital(sample_case().history, "USD m")
    assert wc.layout.yaxis2.title.text == "Days of revenue"
    assert wc.layout.barmode == "relative"


def test_area_controls_keep_original_amounts_and_earnings_units(monkeypatch):
    import valuation.plotly_charts as pc
    from valuation.statements import Line

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    case = sample_case()
    income = pc.plot_income_stack(case.history, "USD m")
    margins = income.layout.updatemenus[0].buttons[1]
    indices = margins.args[2]
    revenue = case.history.income.loc[Line.REVENUE].to_numpy(dtype=float)
    for i, margin in zip(indices, margins.args[0]["y"]):
        np.testing.assert_allclose(margin, np.asarray(income.data[i].y)/revenue*100)
    balance = pc.plot_balance_composition(case.history, "USD m")
    assert balance.layout.updatemenus[0].buttons[1].args[0]["groupnorm"] == "percent"
    for trace in balance.data:
        np.testing.assert_allclose(np.asarray(trace.customdata)[:, 2], trace.y)


def test_surface_outside_base_uses_labeled_midpoint_slices(monkeypatch):
    import valuation.plotly_charts as pc

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    x, y = np.meshgrid([1., 2., 3.], [1., 2., 3.])
    fig = pc.plot_surface_panel(x, y, x+y, xlabel="X", ylabel="Y", zlabel="Z",
                               title="Outside", mark=(10., 10., 20.))
    assert "base inputs outside displayed range" in fig.layout.title.text
    assert "midpoint inputs" in fig.layout.title.text
    assert not any(t.name and t.name.startswith("Base case") for t in fig.data)


def test_forecast_surfaces_reconcile_to_dcf_and_individual_scenarios():
    from dataclasses import replace
    import pytest
    from valuation.plots import forecast_dcf_surface
    from valuation.dcf import present_value, discount_factor, net_debt, unlevered_fcf
    from valuation.statements import forecast_statements, Line

    for mid_year in (False, True):
        case = sample_case()
        case.assumptions = replace(case.assumptions, mid_year=mid_year, exit_ev_ebitda=24.)
        dcf = run_dcf(case)
        forecast = forecast_statements(case).statements
        flows = unlevered_fcf(case, forecast.income, forecast.cashflow).tolist()
        for method, terminal, base in (("gordon", case.assumptions.terminal_growth, dcf.gordon_price),
                                       ("exit", 24., dcf.exit_price)):
            x, y, z = forecast_dcf_surface(case, method=method, wacc_steps=8, terminal_steps=6)
            assert z.shape == (6, 8)
            base_x = np.flatnonzero(x[0] == dcf.wacc)[0]
            base_y = np.flatnonzero(y[:, 0] == terminal)[0]
            assert z[base_y, base_x] == pytest.approx(base)
            rate, assumption = x[-1, -1], y[-1, -1]
            tv = (flows[-1]*(1+assumption)/(rate-assumption) if method == "gordon" else
                  float(forecast.income.loc[Line.EBITDA].iloc[-1])*assumption)
            expected = (present_value(flows, rate, mid_year)
                        + tv*discount_factor(len(flows), rate, mid_year)-net_debt(case))/case.shares
            assert z[-1, -1] == pytest.approx(expected)


def test_forecast_surface_masks_invalid_gordon_region_and_validates_inputs():
    import pytest
    from valuation.plots import forecast_dcf_surface

    case = sample_case()
    x, y, z = forecast_dcf_surface(case, wacc_steps=7, terminal_steps=9, growth_span=.12)
    assert (x <= y).any()
    assert np.isnan(z[x <= y]).all()
    assert np.isfinite(z[x > y]).all()
    with pytest.raises(ValueError, match="method"):
        forecast_dcf_surface(case, method="unknown")
    with pytest.raises(ValueError, match="three grid"):
        forecast_dcf_surface(case, wacc_steps=2)
    with pytest.raises(ValueError, match="positive"):
        forecast_dcf_surface(case, growth_span=0)


def test_surface_local_slopes_use_displayed_units_and_do_not_fill_gaps():
    from valuation.chart_data import surface_diagnostics

    x, y = np.meshgrid([1., 2., 4., 8.], [10., 13., 20., 25.])
    z = 2*x + 3*y
    diagnostics = surface_diagnostics(x, y, z, reference=42.)
    np.testing.assert_allclose(diagnostics[:, :, 0], z-42)
    np.testing.assert_allclose(diagnostics[:, :, 1], 2.)
    np.testing.assert_allclose(diagnostics[:, :, 2], 3.)
    z[1, 1] = np.nan
    assert np.isnan(surface_diagnostics(x, y, z)[1, 1]).all()


def test_surface_slider_frames_update_only_their_own_slice(monkeypatch):
    import valuation.plotly_charts as pc

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    x, y = np.meshgrid([1., 2., 3.], [10., 20., 30.])
    z = 2*x + 3*y
    fig = pc.plot_surface_panel(x, y, z, xlabel="X", ylabel="Y", zlabel="Value", title="Controls",
                               mark=(2., 20., 64.), reference=70., reference_label="Target")
    assert len(fig.layout.sliders) == 2
    assert fig.layout.meta["valid_scenarios"] == 9
    groups = []
    for col, slider in enumerate(fig.layout.sliders, start=1):
        frame = next(f for f in fig.frames if f.name == slider.steps[-1].args[0][0])
        groups.append(set(frame.traces))
        assert [t.type for t in frame.data] == ["scatter", "scatter3d", "scatter"]
        expected = 2*x[0] + 90 if col == 1 else 6 + 3*y[:, 0]
        np.testing.assert_allclose(frame.data[0].y, expected)
        np.testing.assert_allclose(frame.data[1].z, expected)
        for update, index in zip(frame.data, frame.traces):
            assert update.type == fig.data[index].type
    assert groups[0].isdisjoint(groups[1])
    coloring = next(menu for menu in fig.layout.updatemenus if menu.type == "dropdown")
    for button in coloring.buttons:
        assert button.args[1] == (0,) or button.args[1] == [0]
        assert "z" not in button.args[0]  # color modes must never alter valuation geometry
    assert fig.data[0].customdata[0, 0, 0] == z[0, 0] - 70


def test_line_index_control_preserves_actuals_and_missing_observations(monkeypatch):
    import valuation.plotly_charts as pc

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    fig = pc.plot_desk_series(pd.DataFrame({"A": [20., np.nan, 30.], "B": [40., 50., 60.]}))
    values = fig.layout.updatemenus[0].buttons[1].args[0]["y"]
    np.testing.assert_allclose(values, [[100., np.nan, 150.], [100., 125., 150.]], equal_nan=True)
    assert fig.data[0].connectgaps is False
    np.testing.assert_allclose(fig.data[0].customdata[:, 0], [20., np.nan, 30.], equal_nan=True)
    zero = pc.plot_desk_series(pd.DataFrame({"A": [0., 1., 2.]}))
    assert not zero.layout.updatemenus


def test_method_bars_keep_asymmetric_valuation_ranges(monkeypatch):
    import valuation.plotly_charts as pc

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    bridge = pd.DataFrame({"method": ["DCF"], "low": [10.], "mid": [16.], "high": [30.]})
    fig = pc.plot_method_bars(bridge, market_price=20.)
    np.testing.assert_allclose(fig.data[0].error_x.array, [14.])
    np.testing.assert_allclose(fig.data[0].error_x.arrayminus, [6.])
    np.testing.assert_allclose(fig.data[0].customdata[:, 2], [-.2])


def test_direct_series_labels_follow_indexed_values_and_respect_missing_endpoints(monkeypatch):
    import valuation.plotly_charts as pc

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    data = pd.DataFrame({"A": [10., 20.], "B": [40., 60.]}, index=[2025, 2026])
    fig = pc.plot_desk_series(data)
    assert [a.y for a in fig.layout.annotations] == [20., 60.]
    assert fig.layout.yaxis.side == "left"
    indexed = fig.layout.updatemenus[0].buttons[1].args[1]["annotations"]
    assert [a["y"] for a in indexed] == [200., 150.]
    data.loc[2026, "B"] = np.nan
    incomplete = pc.plot_desk_series(data)
    assert not incomplete.layout.annotations
    assert incomplete.layout.showlegend is True


def test_income_legend_links_the_same_measure_across_panels(monkeypatch):
    import valuation.plotly_charts as pc
    from valuation import theme

    monkeypatch.setattr(pc, "show", lambda fig: fig)
    fig = pc.plot_income_stack(sample_case().history)
    ebit = [t for t in fig.data if t.name == "EBIT"]
    assert len(ebit) == 2
    assert ebit[0].legendgroup == ebit[1].legendgroup == "EBIT"
    assert ebit[1].showlegend is False
    assert ebit[1].line.color == theme.FINANCIAL["EBIT"]
