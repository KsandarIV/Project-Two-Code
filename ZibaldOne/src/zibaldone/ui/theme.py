"""Colours, sizes and breakpoints of the interface: Alex's dark neon palette.

Pure data and small colour helpers, no Flet import, so they can be tested
without a display. `zibaldone.ui.widgets.build_theme` turns them into a Flet theme.

Rules for colour:
- body text is TEXT or TEXT_DIM, never a categorical colour;
- the categorical colours (one per mascot and area) mark things: dots, bars,
  avatars, borders. Yellow is only ever an accent;
- text drawn on a coloured fill uses `readable_on(fill)`.
"""

from typing import Sequence, Tuple

BG = "#0D0E15"
PANEL = "#141521"
PANEL_HIGH = "#1A1C2B"  # a panel inside a panel, hovered rows
BORDER = "#1E2035"
TEXT = "#E6F7FF"
TEXT_DIM = "#8A94A8"
ACCENT = "#00E5FF"
ACCENT_2 = "#FF5500"
ERROR = "#FF6B8B"  # a softer pink-red, readable on the dark panels
SUCCESS = "#74EE15"

# One colour per mascot / area, in this order.
CATEGORICAL: Tuple[str, ...] = ("#B3F3F6", "#FF5500", "#FFFF00", "#FF0000", "#74EE15", "#FF007F", "#8A2BE2")
YELLOW = "#FFFF00"

RADIUS = 12
RADIUS_SMALL = 10
PAD = 16
GAP = 12

# Below this width (logical pixels) the app uses the phone layout (bottom bar).
WIDE_MIN_WIDTH = 720
# Breakpoints of the centred content column (ResponsiveRow `col`).
CONTENT_COLUMNS = {"xs": 12, "lg": 11, "xl": 10, "xxl": 8}


def _channels(color: str) -> Tuple[int, int, int]:
    text = color.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"colore non valido: '{color}' (usa #RRGGBB)")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def relative_luminance(color: str) -> float:
    """WCAG relative luminance of a #RRGGBB colour (0 = black, 1 = white)."""

    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in _channels(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: str, second: str) -> float:
    """WCAG contrast ratio, from 1 (same colour) to 21 (black on white)."""
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def readable_on(fill: str) -> str:
    """The text colour (BG or TEXT) with the best contrast on `fill`."""
    return BG if contrast_ratio(BG, fill) >= contrast_ratio(TEXT, fill) else TEXT


def category_color(index: int) -> str:
    return CATEGORICAL[index % len(CATEGORICAL)]


def color_or(color: str, fallback: str = ACCENT) -> str:
    """The template's own colour when it is a valid #RRGGBB, else `fallback`."""
    try:
        _channels(color or "")
    except ValueError:
        return fallback
    return color


def accent_text_color(color: str, background: str = PANEL) -> str:
    """A categorical colour used as text only when it stays readable, never yellow."""
    if color.upper() == YELLOW or contrast_ratio(color, background) < 4.5:
        return TEXT
    return color


def palette_contrasts(colors: Sequence[str], background: str = BG) -> Tuple[float, ...]:
    return tuple(round(contrast_ratio(color, background), 2) for color in colors)
