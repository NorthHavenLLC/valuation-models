"""Institutional quant figure theme — one palette for Plotly and matplotlib.

Design intent: research note / risk memo, not a dashboard.
Black ink, cool gray rules, one blue series accent, one red for losses.
"""

from __future__ import annotations

PAPER = "#ffffff"
PLOT = "#ffffff"
INK = "#182b3a"
MUTE = "#647582"
RULE = "#ced8df"
GRID = "#e9eef2"
SOFT = "#f7f9fb"
FOG = "#edf2f6"

# Series: ink, accent blue, muted gray, loss red, secondary blue-gray, warm gray
ACCENT = "#285f91"
STEEL = "#7995ae"
NEG = "#b3524b"
POS = "#387d76"
SLATE = "#8b99a7"
WARM = "#bd9152"

NAVY = ACCENT
BLUE = ACCENT
RUST = NEG
CORAL = NEG
OLIVE = POS
GREEN = POS
AMBER = WARM
ORANGE = WARM
TEAL = POS

SERIES = [ACCENT, POS, WARM, STEEL, NEG, INK, SLATE]

# Sequential: white → steel → accent (no rainbow)
SCALE_SEQ = [
    [0.0, "#ffffff"],
    [0.2, "#e8eef4"],
    [0.45, "#9db4c9"],
    [0.7, "#3d6a8f"],
    [1.0, "#0f2f52"],
]
# Diverging: red ← white → blue
SCALE_DIV = [
    [0.0, "#b3524b"],
    [0.35, "#e8c8c8"],
    [0.5, "#ffffff"],
    [0.65, "#c8d6e4"],
    [1.0, "#285f91"],
]
# Surface: single-hue blue (readable when orbiting)
SCALE_SURFACE = [
    [0.0, "#eef3f8"],
    [0.25, "#b7c9db"],
    [0.5, "#6a8faf"],
    [0.75, "#2a5f8a"],
    [1.0, "#0f2f52"],
]

FONT_TITLE = "Helvetica Neue, Helvetica, Arial, sans-serif"
FONT_BODY = "Helvetica Neue, Helvetica, Arial, sans-serif"

PALETTE = {
    "ink": INK,
    "mute": MUTE,
    "blue": ACCENT,
    "orange": WARM,
    "green": POS,
    "teal": POS,
    "amber": WARM,
    "coral": NEG,
    "slate": SLATE,
    "fog": FOG,
    "grid": GRID,
    "soft": SOFT,
    "rule": RULE,
    "paper": PAPER,
    "steel": STEEL,
}


def mpl_cmaps():
    from matplotlib import colors

    return {
        "seq": colors.LinearSegmentedColormap.from_list("q_seq", [c[1] for c in SCALE_SEQ]),
        "div": colors.LinearSegmentedColormap.from_list("q_div", [c[1] for c in SCALE_DIV]),
        "surface": colors.LinearSegmentedColormap.from_list("q_surf", [c[1] for c in SCALE_SURFACE]),
    }


def rgba(hex_color: str, alpha: float) -> str:
    """Use the same series color for an opaque line and a translucent area."""
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"

# Financial meanings stay stable across composition and earnings panels.
FINANCIAL = {"COGS": "#a9b9c6", "OpEx": "#788fa1", "D&A": "#d3dce2",
             "Revenue": INK, "EBIT": POS, "EBITDA": ACCENT, "Net income": WARM}
