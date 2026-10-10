"""Interactive equity picker for notebook 00.

Dropdown + optional ticker box writes ``cases/active.yaml`` and refreshes
``case`` / ``UNIT`` in the IPython user namespace so 01–06 stay in sync.
"""

from __future__ import annotations

from typing import Any

from IPython.display import clear_output, display
import ipywidgets as widgets

from valuation.active import (
    equity_choices,
    open_active_case,
    resolve_active,
    set_active_custom,
    set_active_equity,
)
from valuation.case import Case
from valuation.report import show_active_card


def _push_ns(case: Case) -> None:
    try:
        from IPython import get_ipython

        ip = get_ipython()
        if ip is not None:
            ip.user_ns["case"] = case
            ip.user_ns["UNIT"] = case.unit
            ip.user_ns["ACTIVE"] = resolve_active()
    except Exception:
        pass


def bind_compact_switcher() -> Case:
    """Thin dropdown for every model notebook — one click switches the whole project."""
    choices = equity_choices()
    # Drop the "Custom ticker…" row here; use notebook 00 for custom.
    choices = [(label, key) for label, key in choices if key != "custom"]
    labels = [label for label, _ in choices]
    value_by_label = {label: key for label, key in choices}
    label_by_value = {key: label for label, key in choices}

    current = resolve_active()
    preset = current["preset"] if current["preset"] in label_by_value else "micron"
    if preset not in label_by_value:
        preset = choices[0][1]

    dropdown = widgets.Dropdown(
        options=labels,
        value=label_by_value[preset],
        description="Model",
        layout=widgets.Layout(width="380px"),
        style={"description_width": "55px"},
    )
    status = widgets.HTML(value="")
    out = widgets.Output()

    def refresh(change: dict[str, Any] | None = None) -> None:
        with out:
            clear_output(wait=True)
            key = value_by_label[dropdown.value]
            set_active_equity(key)
            case = open_active_case(show=False)
            _push_ns(case)
            spec = resolve_active()
            status.value = (
                f"<span style='font-family:Helvetica,Arial,sans-serif;font-size:0.9rem;"
                f"color:var(--vscode-editor-foreground, #e8eaed)'>"
                f"<strong>{spec['label']}</strong>"
                f"{' · ' + spec['ticker'] if spec['ticker'] else ''}"
                f" · active for all notebooks</span>"
            )
            show_active_card(case, spec)

    dropdown.observe(lambda c: refresh(c) if c.get("name") == "value" else None, names="value")
    display(widgets.HBox([dropdown]), status, out)
    refresh()
    return open_active_case(show=False)


def bind_equity_switcher(*, auto: bool = True) -> Case:
    """Show a legible equity picker and return the current case.

    Changing the dropdown (or clicking Apply on a typed ticker) updates
    ``cases/active.yaml`` and rebinds ``case`` / ``UNIT`` in the notebook.
    """
    choices = equity_choices()
    labels = [label for label, _ in choices]
    value_by_label = {label: key for label, key in choices}
    label_by_value = {key: label for label, key in choices}

    current = resolve_active()
    preset = current["preset"]
    if preset not in label_by_value:
        preset = "custom" if preset == "custom" else "micron"
        if preset not in label_by_value:
            preset = choices[0][1]

    dropdown = widgets.Dropdown(
        options=labels,
        value=label_by_value.get(preset, labels[0]),
        description="Equity",
        layout=widgets.Layout(width="340px"),
        style={"description_width": "60px"},
    )
    ticker = widgets.Text(
        value=current["ticker"] or "",
        placeholder="e.g. MU  (overrides dropdown when Apply)",
        description="Ticker",
        layout=widgets.Layout(width="220px"),
        style={"description_width": "55px"},
    )
    peers = widgets.Text(
        value=", ".join(current["peers"]),
        placeholder="peers, comma-separated",
        description="Peers",
        layout=widgets.Layout(width="320px"),
        style={"description_width": "50px"},
    )
    apply_btn = widgets.Button(
        description="Apply",
        button_style="primary",
        layout=widgets.Layout(width="90px", height="32px"),
    )
    status = widgets.HTML(value="")
    out = widgets.Output()

    def _load(key: str, *, custom_ticker: str | None = None, peer_list: list[str] | None = None) -> Case:
        if custom_ticker:
            set_active_custom(custom_ticker, peers=peer_list)
        elif key == "custom":
            set_active_custom(custom_ticker or ticker.value or None, peers=peer_list)
        else:
            set_active_equity(key)
        case = open_active_case(show=False)
        _push_ns(case)
        return case

    def _parse_peers(text: str) -> list[str]:
        return [p.strip().upper() for p in text.split(",") if p.strip()]

    def refresh(from_dropdown: bool = True) -> None:
        with out:
            clear_output(wait=True)
            try:
                typed = ticker.value.strip().upper()
                peer_list = _parse_peers(peers.value)
                if not from_dropdown and typed:
                    case = _load("custom", custom_ticker=typed, peer_list=peer_list or None)
                else:
                    key = value_by_label[dropdown.value]
                    if key == "custom":
                        case = _load("custom", custom_ticker=typed or None, peer_list=peer_list or None)
                    else:
                        case = _load(key)
                spec = resolve_active()
                # Keep controls aligned with what we just wrote.
                if spec["preset"] in label_by_value:
                    dropdown.value = label_by_value[spec["preset"]]
                ticker.value = spec["ticker"] or ""
                peers.value = ", ".join(spec["peers"])
                status.value = (
                    f"<span style='color:var(--vscode-testing-iconPassed,#3d9a5f);"
                    f"font-family:Helvetica,Arial,sans-serif;font-size:0.85rem'>"
                    f"Active → {spec['label']}"
                    f"{' · ' + spec['ticker'] if spec['ticker'] else ''}"
                    f" · re-run notebooks 01–06</span>"
                )
                show_active_card(case, spec)
            except Exception as exc:  # noqa: BLE001 — surface load errors in the panel
                status.value = (
                    f"<span style='color:var(--vscode-errorForeground,#f14c4c);"
                    f"font-family:Helvetica,Arial,sans-serif;font-size:0.85rem'>"
                    f"Could not load: {exc}</span>"
                )

    def on_dropdown(change: dict[str, Any]) -> None:
        if change.get("name") != "value":
            return
        key = value_by_label[change["new"]]
        if key != "custom":
            ticker.value = ""
        refresh(from_dropdown=True)

    def on_apply(_: Any = None) -> None:
        refresh(from_dropdown=False)

    dropdown.observe(on_dropdown, names="value")
    apply_btn.on_click(on_apply)
    ticker.on_submit(lambda _: on_apply())

    row = widgets.HBox(
        [dropdown, ticker, peers, apply_btn],
        layout=widgets.Layout(flex_flow="row wrap", align_items="center"),
    )
    display(row, status, out)

    if auto:
        refresh(from_dropdown=True)

    return open_active_case(show=False)
