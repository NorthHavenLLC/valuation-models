from valuation.active import (
    equity_choices,
    list_presets,
    resolve_active,
    set_active_custom,
    set_active_equity,
    set_active_preset,
)


def test_presets_include_micron():
    presets = list_presets()
    assert "micron" in presets
    assert presets["micron"]["ticker"] == "MU"
    assert "AVGO" in presets["micron"]["peers"]
    assert presets["micron"]["segments"]


def test_active_yaml_resolves(tmp_path=None):
    # Default project active.yaml should be a known preset.
    spec = resolve_active()
    assert spec["preset"] in set(list_presets()) | {"custom"}
    assert "label" in spec


def test_set_active_preset_roundtrip():
    before = resolve_active()["preset"]
    try:
        set_active_preset("sample")
        assert resolve_active()["ticker"] is None
        set_active_preset("micron")
        assert resolve_active()["ticker"] == "MU"
    finally:
        set_active_preset(before)


def test_set_active_equity_accepts_ticker_or_preset():
    before = resolve_active()["preset"]
    try:
        assert set_active_equity("MU")["preset"] == "micron"
        assert set_active_equity("apple")["ticker"] == "AAPL"
        assert set_active_custom("TXN", peers=["ADI", "QCOM"])["preset"] == "custom"
        assert resolve_active()["ticker"] == "TXN"
        assert resolve_active()["peers"] == ["ADI", "QCOM"]
        labels = [label for label, _ in equity_choices()]
        assert any("Micron" in label for label in labels)
    finally:
        set_active_preset(before)
