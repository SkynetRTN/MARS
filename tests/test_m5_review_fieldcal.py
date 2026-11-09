"""Native calibration regressions from the M5 follow-up review."""
from datetime import datetime

import numpy as np
import pytest
import sep
from astropy.wcs import WCS

from algorithms.catalogs.schemas import CatalogSource, Mag
from algorithms.fieldcal.field_cal import perform_field_calibration
from algorithms.fieldcal.schemas import PhotometricCalibrationSettings
from algorithms.photometry.photometry import run_photometry
from algorithms.photometry.schemas import (
    PhotometrySettings, SourceExtractionData, SourceExtractionSettings,
)
from algorithms.photometry.source_extraction import run_source_extraction


def _field():
    wcs = WCS(naxis=2)
    wcs.wcs.crpix = [60, 60]
    wcs.wcs.crval = [180, 0]
    wcs.wcs.cdelt = [-1/3600, 1/3600]
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    header = wcs.to_header()
    header["FILTER"], header["EXPTIME"] = "V", 1
    yy, xx = np.indices((120, 120))
    # Detector-dependent noise makes a shifted/padded ROI RMS detectably wrong.
    image = 100 + np.random.default_rng(10).normal(size=xx.shape)*(1 + yy/12)
    catalog, detections = [], []
    for i, (x, y) in enumerate([(40, 27), (80, 27), (40, 95), (80, 95)]):
        image += (1000 + i*50)*np.exp(-((xx-x+1)**2 + (yy-y+1)**2)/8)
        ra, dec = wcs.all_pix2world(x, y, 1)
        catalog.append(CatalogSource(
            id=str(i), ra_hours=ra/15, dec_degs=dec, catalog_name="APASS",
            mags={"V": Mag(value=12 + i*.1, error=.02)},
        ))
        detections.append(SourceExtractionData(
            id="d"+str(i), x=x, y=y, ra_hours=ra/15, dec_degs=dec,
        ))
    return image, header, wcs, catalog, detections


@pytest.mark.parametrize("masked", [False, True])
def test_cropped_extraction_uses_full_detector_rms_and_annular_sky(masked):
    image, header, wcs, catalog, _ = _field()
    if masked:
        mask = np.zeros(image.shape, dtype=bool)
        mask[12:20, 32:48] = True
        image[mask] = 1e8
        image = np.ma.array(image, mask=mask)
    extraction = SourceExtractionSettings(
        x=1, y=21, width=120, height=80, bk_size=24, bk_filter_size=1,
    )
    photometry = PhotometrySettings(a=4, a_in_px=6, a_out_px=10, apcorr_tol=0)
    detected, _, cropped_rms = run_source_extraction(image, header, extraction)
    assert len(detected) == 4
    assert cropped_rms.shape == (80, 120)
    # The full-image annuli extend beyond the extraction ROI.
    assert any(s.y-10 < 21 or s.y+10 > 100 for s in detected)
    # Independent SEP oracle in global detector coordinates, respecting masks.
    rms = sep.Background(
        np.ma.getdata(image), mask=np.ma.getmaskarray(image) if masked else None,
        bw=24, bh=24, fw=1, fh=1,
    ).rms()
    expected = run_photometry(
        image, header.copy(),
        [s.model_copy(update={"ra_hours": None, "dec_degs": None}) for s in detected],
        photometry, wcs=wcs, background=None, background_rms=rms,
    )
    zero_point, result = perform_field_calibration(
        header.copy(), image, wcs=wcs, catalog_sources=catalog,
        extraction_settings=extraction, photometry_settings=photometry,
        field_cal_settings=PhotometricCalibrationSettings(variable_check_tol=0),
    )
    assert np.isfinite(zero_point)
    actual = sorted(result.phot_results, key=lambda s: (s.y, s.x))
    expected = sorted(expected, key=lambda s: (s.y, s.x))
    assert len(actual) == len(expected) == 4
    np.testing.assert_allclose(
        [(s.flux, s.flux_error, s.mag_error) for s in actual],
        [(s.flux, s.flux_error, s.mag_error) for s in expected], rtol=1e-12,
    )


@pytest.mark.parametrize("pixel_position", ["absent", "nan", "partial", "finite"])
def test_sky_only_observations_survive_matching_and_lazy_header_projection(pixel_position):
    image, header, _, catalog, observed = _field()
    header["DATE-OBS"] = "2020-01-02T00:00:00"
    # Catalog motion affects association, but must not move an observed position
    # again when metadata from the matched catalog row is copied over.
    for source in catalog:
        source.pm_epoch = datetime(2020, 1, 1)
        source.pm_sky = 1/(3600*86400)
        source.pm_pos_angle_sky = 0
        source.pm_pixel = 1/86400
        source.pm_pos_angle_pixel = 0
    detections = []
    for source in observed:
        x = source.x if pixel_position in ("partial", "finite") else (
            np.nan if pixel_position == "nan" else None)
        y = source.y if pixel_position == "finite" else (
            np.nan if pixel_position == "nan" else None)
        update = {"x": x, "y": y}
        if pixel_position == "finite":
            # Sky metadata may be stale: valid measured pixels take priority.
            update["ra_hours"] = source.ra_hours + 2/(15*3600)
        detections.append(source.model_copy(update=update))
    photometry = PhotometrySettings(a=4, a_in_px=6, a_out_px=10, apcorr_tol=0)
    expected = run_photometry(image, header.copy(), observed, photometry)
    zero_point, result = perform_field_calibration(
        header.copy(), image, catalog_sources=catalog, detected_sources=detections,
        photometry_settings=photometry,
        field_cal_settings=PhotometricCalibrationSettings(
            variable_check_tol=0, source_match_tol_arcsec=5),
    )
    assert np.isfinite(zero_point)
    actual = sorted(result.phot_results, key=lambda s: s.id)
    assert len(actual) == len(expected) == 4
    np.testing.assert_allclose(
        [(s.x, s.y, s.flux, s.flux_error) for s in actual],
        [(s.x, s.y, s.flux, s.flux_error) for s in expected], rtol=1e-10,
    )
