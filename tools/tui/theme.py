"""The console's colours: the official Skynet palette, as two Textual themes.

MARS stays visibly part of Skynet (``docs/working/mars-rebrand.md`` §4), so
the console takes the palette the brand assets use, by exact hex value --
never sampled from a raster. Every widget styles itself through Textual's
theme variables (``$accent``, ``$surface``, ``$panel``, ``$text-muted``), so
the themes below are the only place a console colour is chosen.

The palette has no red and no green. ``error`` and ``success`` are left at
Textual's defaults so that a failure still reads as a failure; recolouring
them in navy and gold would trade meaning for brand.
"""

from __future__ import annotations

from textual.theme import Theme

__all__ = [
    "BRAND_NAVY",
    "DEEP_NIGHT_BLUE",
    "MARS_DARK",
    "MARS_LIGHT",
    "MIST_BLUE",
    "NAVY_BANNER",
    "OFF_WHITE",
    "SLATE_SKY_BLUE",
    "SOFT_APRICOT",
    "THEMES",
    "WARM_GOLD",
    "waveform_color",
]

#: The Skynet palette (beamer/beamercolorthemeskynet.sty).
BRAND_NAVY = "#2B3345"
NAVY_BANNER = "#1F2633"
DEEP_NIGHT_BLUE = "#35556E"
SLATE_SKY_BLUE = "#5E86A4"
MIST_BLUE = "#B8D2E1"
WARM_GOLD = "#D99633"
SOFT_APRICOT = "#EFC48A"
OFF_WHITE = "#F7F6F2"

#: The same template's derived dark-mode interface surfaces. Not palette
#: colours -- surfaces the template itself layers the palette on.
_DARK_SURFACE_1 = "#353E52"
_DARK_SURFACE_2 = "#414B60"

#: The default: the banner's navy plate, gold frames, off-white text.
MARS_DARK = Theme(
    name="mars",
    primary=SLATE_SKY_BLUE,
    secondary=DEEP_NIGHT_BLUE,
    accent=WARM_GOLD,
    warning=SOFT_APRICOT,
    foreground=OFF_WHITE,
    background=NAVY_BANNER,
    surface=BRAND_NAVY,
    panel=_DARK_SURFACE_1,
    boost=_DARK_SURFACE_2,
    dark=True,
)

#: For a light terminal: off-white ground, navy text, the same gold frames.
MARS_LIGHT = Theme(
    name="mars-light",
    primary=DEEP_NIGHT_BLUE,
    secondary=SLATE_SKY_BLUE,
    accent=WARM_GOLD,
    warning=WARM_GOLD,
    foreground=BRAND_NAVY,
    background=OFF_WHITE,
    surface=OFF_WHITE,
    panel=MIST_BLUE,
    dark=False,
)

THEMES = (MARS_DARK, MARS_LIGHT)


def waveform_color(dark: bool) -> str:
    """The sonification preview's colour on a dark or a light ground.

    A Rich ``Text`` style cannot name a theme variable, so the preview is
    given a literal -- chosen here, per ground. Mist Blue on the light
    theme's off-white is about 1.4:1 and all but invisible; Deep Night Blue
    is the palette's legible blue there.
    """

    return MIST_BLUE if dark else DEEP_NIGHT_BLUE
