"""Detector-pixel saturation counts through native SEP extraction."""
from __future__ import annotations

import numpy as np
import pytest

from algorithms.skylib_lite.extraction.main import extract_sources


@pytest.mark.parametrize("downsample,expected", [(1, 6), (2, 4), (3, 3)])
@pytest.mark.parametrize("kind", ["boolean", "integer", "masked"])
def test_saturation_counts_use_only_detector_pixels_in_retained_blocks(downsample, expected, kind):
    yy, xx = np.indices((65, 67))
    image = 100 + np.random.default_rng(19).normal(0, 1, xx.shape)
    image += 10000*np.exp(-((xx-62)**2 + (yy-59)**2)/18)
    saturation = np.zeros(image.shape, dtype=bool if kind == "boolean" else int)
    # The last column and last two rows form incomplete blocks at factor 3.
    # Factor 2 retains row 63; factor 1 retains all six marked detector pixels.
    for y, x in ((59, 63), (59, 64), (59, 65), (59, 66), (63, 63), (64, 63)):
        saturation[y, x] = 1 if kind == "boolean" else 7
    if kind == "masked":
        mask = np.zeros(image.shape, dtype=bool)
        mask[59, 64] = True
        saturation = np.ma.array(saturation, mask=mask)
        expected -= 1

    sources, _, _ = extract_sources(
        image, downsample=downsample, threshold=5,
        bkg_kw=dict(size=256, filter_size=3), fwhm=0, min_pixels=9,
        min_fwhm=0, max_fwhm=0, max_ellipticity=0, clean=0,
        centroid=False, sat_img=saturation,
    )
    source = sources[np.argmax(sources["flux"])]
    assert source["x"] > 55 and source["y"] > 55
    assert source["saturated"] == expected
    assert sources["saturated"].sum() == expected
