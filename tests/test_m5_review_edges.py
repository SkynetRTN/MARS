"""Fractional FITS positions occupy the full continuous detector footprint."""
import numpy as np
import pytest

from algorithms.photometry.photometry import run_photometry
from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData


@pytest.mark.parametrize("x,y", [
    (.9, 10), (30.1, 10), (15, .9), (15, 20.1),
    (.9, .9), (30.1, 20.1), (1, 1), (30, 20),
])
def test_fractional_edge_centers_measure_contained_apertures(x, y):
    image = np.full((20, 30), 100.)
    rows = run_photometry(
        image, {"EXPTIME": 1}, [SourceExtractionData(x=x, y=y)],
        PhotometrySettings(a=.2, apcorr_tol=0),
        background=np.zeros_like(image), background_rms=np.ones_like(image),
    )
    assert len(rows) == 1
    assert (rows[0].x, rows[0].y) == (x, y)
    assert rows[0].flux == pytest.approx(100*np.pi*.2**2, abs=1e-11)


@pytest.mark.parametrize("x,y", [(.49, 10), (30.51, 10), (15, .49), (15, 20.51)])
def test_centers_outside_continuous_footprint_are_rejected(x, y):
    image = np.full((20, 30), 100.)
    with pytest.raises(ValueError, match="Missing WCS and no source XYs given"):
        run_photometry(
            image, {}, [SourceExtractionData(x=x, y=y)],
            PhotometrySettings(a=.2, apcorr_tol=0),
            background=np.zeros_like(image), background_rms=np.ones_like(image),
        )
