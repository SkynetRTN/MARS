#!/usr/bin/env python3
"""Export the MARS brand assets from the masters in ``brand/``.

``brand/square_mark.png`` and ``brand/github_social_preview.png`` are the
maintainer's masters. Everything else is exported from them, never redrawn:

- ``docs/assets/mars-banner.png`` -- the README banner, 1760x360 (shown at
  880x180): the mark beside the wordmark and tagline, lifted from the social
  preview by unmixing them from its background, on the Skynet palette's
  Navy (banner). Its own background makes one file right in both themes.
- ``docs/assets/mars-mark.png`` -- the mark at 512x512, for documentation.
- ``tools/mcp/icons/mars-{64,128}.png`` -- the MCP server's icons, shipped in
  the wheel (``docs/archive/mars-rebrand.md`` §4).

Re-run after changing a master:

    uv run python docs/assets/make_brand.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "brand"

#: Skynet palette, docs/archive/mars-rebrand.md §4.
NAVY_BANNER = (0x1F, 0x26, 0x33)

#: The social preview's background, and where its wordmark and tagline sit.
PREVIEW_BACKGROUND = np.array([28, 37, 53], float)
WORDMARK_ROWS, TAGLINE_ROWS, TEXT_COLUMNS = (212, 364), (376, 418), (598, 1164)


def _mark() -> Image.Image:
    mark = Image.open(BRAND / "square_mark.png").convert("RGBA")
    return mark.crop(mark.getbbox())


def _cutout(preview: np.ndarray, rows: tuple[int, int]) -> Image.Image:
    """One line of text as its own colour over an alpha unmixed from the plate."""

    region = preview[rows[0] : rows[1], TEXT_COLUMNS[0] : TEXT_COLUMNS[1]]
    distance = np.abs(region - PREVIEW_BACKGROUND).sum(2)
    ink = region[distance > distance.max() * 0.9].mean(0)
    alpha = np.clip(distance / np.abs(ink - PREVIEW_BACKGROUND).sum(), 0, 1)
    rgba = np.dstack([np.broadcast_to(ink, region.shape), alpha * 255]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def banner(width: int = 1760, height: int = 360) -> Image.Image:
    preview = np.asarray(
        Image.open(BRAND / "github_social_preview.png").convert("RGB")
    ).astype(float)
    text = Image.new("RGBA", (566, 206), (0, 0, 0, 0))
    text.alpha_composite(_cutout(preview, WORDMARK_ROWS), (0, 0))
    text.alpha_composite(_cutout(preview, TAGLINE_ROWS), (0, 164))
    text = text.crop(text.getbbox())

    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    plate = Image.new("L", (width, height), 0)
    ImageDraw.Draw(plate).rounded_rectangle((0, 0, width - 1, height - 1), radius=24, fill=255)
    out.paste(Image.new("RGBA", (width, height), NAVY_BANNER + (255,)), (0, 0), plate)

    mark_height, text_height, gap = 290, 232, 72
    mark = _mark()
    mark = mark.resize((round(mark.width * mark_height / mark.height), mark_height), Image.LANCZOS)
    text = text.resize((round(text.width * text_height / text.height), text_height), Image.LANCZOS)
    x = (width - (mark.width + gap + text.width)) // 2
    out.alpha_composite(mark, (x, (height - mark_height) // 2))
    out.alpha_composite(text, (x + mark.width + gap, (height - text_height) // 2))
    return out


def square(side: int) -> Image.Image:
    mark = _mark()
    extent = max(mark.size)
    canvas = Image.new("RGBA", (extent, extent), (0, 0, 0, 0))
    canvas.alpha_composite(mark, ((extent - mark.width) // 2, (extent - mark.height) // 2))
    return canvas.resize((side, side), Image.LANCZOS)


def main() -> None:
    banner().save(ROOT / "docs/assets/mars-banner.png", optimize=True)
    square(512).save(ROOT / "docs/assets/mars-mark.png", optimize=True)
    for side in (64, 128):
        square(side).save(ROOT / f"tools/mcp/icons/mars-{side}.png", optimize=True)


if __name__ == "__main__":
    main()
