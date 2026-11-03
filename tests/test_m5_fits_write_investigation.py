"""M5 FITS write investigation at a4d429a: controls and bug characterizations.

These bounded, synthetic frames exercise real Astropy serialization and both
maintained writers. Tests named ``characterization`` deliberately pin surviving
cards or incorrect output; their passing is not evidence that those defects
are fixed. The public-tool test replaces the solver seam only and provides no
evidence of native solver success. TAN/SIP controls compute their own detector
polynomial and inverse gnomonic projection, independently of WCSLIB.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest
from astropy import units as u
from astropy.coordinates import FK4, FK5, ICRS, SkyCoord
from astropy.io import fits
from astropy.wcs import DistortionLookupTable, FITSFixedWarning, Sip, WCS

from algorithms.wcs.header_utils import guess_icrs_radec_from_header
from algorithms.wcs.results import WcsSolveMetadata, WcsSolveResult
from algorithms.wcs.source_extraction import _SIP_KEY_REGEX, build_wcs_from_header
from algorithms.wcs.wcs import WCS_REGEX, _accept_solution, _write_wcs_to_header
from tools import wcs as public_wcs


SIDE = 64
PIXELS = np.array([[0., 0.], [63., 0.], [0., 63.], [63., 63.], [31.5, 31.5]])
SIP_A20 = 1e-4
SIP_B02 = -2e-4


def _accepted_wcs(frame="ICRS", *, sip=False):
    result = WCS(naxis=2)
    result.wcs.ctype = ["RA---TAN-SIP", "DEC--TAN-SIP"] if sip else ["RA---TAN", "DEC--TAN"]
    result.wcs.crpix = [32.5, 32.5]
    result.wcs.crval = [120., 20.]
    result.wcs.cd = np.diag([-1 / 3600, 1 / 3600])
    result.wcs.radesys = frame
    if sip:
        a = np.zeros((3, 3))
        b = np.zeros((3, 3))
        a[2, 0], b[0, 2] = SIP_A20, SIP_B02
        result.sip = Sip(a, b, None, None, result.wcs.crpix)
    # Acceptance sets WCSLIB's implicit FK4/FK5 equinox before serialization.
    assert _accept_solution(
        result, expected_parity=None, ra_hint_deg=None, dec_hint_deg=None,
        width=SIDE, height=SIDE, max_sep_deg=None,
    ) == (True, None)
    return result


def _expected_icrs(pixels=PIXELS, *, frame="ICRS", sip=False, detector_shift=(0., 0.)):
    """Independent inverse TAN, including explicit SIP and detector shifts."""
    offset = np.asarray(pixels) + 1 - np.array([32.5, 32.5]) + detector_shift
    x, y = offset.T
    if sip:
        x, y = x + SIP_A20 * x**2, y + SIP_B02 * y**2
    xi, eta = np.deg2rad(np.array([-x, y]) / 3600)
    ra0, dec0 = np.deg2rad([120., 20.])
    denominator = np.cos(dec0) - eta * np.sin(dec0)
    ra = ra0 + np.arctan2(xi, denominator)
    dec = np.arctan2(
        np.sin(dec0) + eta * np.cos(dec0), np.hypot(denominator, xi),
    )
    coordinate_frame = {
        "ICRS": ICRS(), "FK5": FK5(equinox="J2000"), "FK4": FK4(equinox="B1950"),
    }[frame]
    return SkyCoord(ra=ra * u.rad, dec=dec * u.rad, frame=coordinate_frame).icrs


def _assert_control(wcs, *, frame="ICRS", sip=False):
    actual = wcs.pixel_to_world(PIXELS[:, 0], PIXELS[:, 1]).icrs
    assert np.max(actual.separation(_expected_icrs(frame=frame, sip=sip)).arcsec) < 2e-7


def _create_frame(path, header):
    data = np.arange(SIDE**2, dtype=np.float32).reshape(SIDE, SIDE)
    fits.PrimaryHDU(data=data, header=header).writeto(path)
    return data


def _write_existing(path, accepted, writer):
    if writer == "algorithm":
        with fits.open(path, mode="update", memmap=False) as hdul:
            _write_wcs_to_header(hdul[0].header, accepted)
            hdul.flush()
    else:
        public_wcs._write_wcs_header(
            path, accepted, expected_version=public_wcs._file_version(path),
        )


@pytest.mark.parametrize("writer", ["algorithm", "tool"])
@pytest.mark.parametrize("frame", ["ICRS", "FK5", "FK4"])
def test_accepted_frame_survives_old_epoch_cards_and_repeated_fits_writes(tmp_path, writer, frame):
    """Controls narrow WCS-18: old frame cards do not move accepted coordinates.

    ICRS explicitly overrides old frame declarations; FK4/FK5 acceptance fills
    their equinox, which is then written over the obsolete one. Obsolete cards
    still surviving below are a characterized metadata-cleanup gap.
    """
    accepted = _accepted_wcs(frame)
    _assert_control(accepted, frame=frame)
    path = tmp_path / f"{writer}-{frame}.fits"
    header = _accepted_wcs("FK4").to_header()
    header["EQUINOX"] = 1900.
    header["RADECSYS"] = "FK4"
    header["EPOCH"] = 1900.
    _create_frame(path, header)

    for _ in range(3):
        _write_existing(path, accepted, writer)
        reread = fits.getheader(path)
        assert reread["RADECSYS"] == "FK4"
        assert reread["EPOCH"] == 1900.
        assert reread["RADESYS"] == frame
        assert reread["EQUINOX"] == {"ICRS": 1900., "FK5": 2000., "FK4": 1950.}[frame]
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*RADECSYS.*", category=FITSFixedWarning)
            reopened = WCS(reread)
        _assert_control(reopened, frame=frame)
        ra, dec = guess_icrs_radec_from_header(reread)
        hinted = SkyCoord(ra * u.deg, dec * u.deg)
        assert hinted.separation(_expected_icrs(np.array([[31.5, 31.5]]), frame=frame)[0]).arcsec < 2e-7


@pytest.mark.parametrize("writer", ["algorithm", "tool"])
@pytest.mark.parametrize("old_sip,new_sip", [(True, True), (True, False), (False, True)])
def test_sip_roundtrip_control_and_dmax_characterization(tmp_path, writer, old_sip, new_sip):
    """SIP geometry is replaced correctly; old DMAX cards are only metadata here."""
    accepted = _accepted_wcs(sip=new_sip)
    _assert_control(accepted, sip=new_sip)
    header = _accepted_wcs(sip=old_sip).to_header(relax=True)
    if old_sip:
        header["A_ORDER"] = 3
        header["A_3_0"] = 1e-5
        assert _accept_solution(
            WCS(header), expected_parity=None, ra_hint_deg=None, dec_hint_deg=None,
            width=SIDE, height=SIDE, max_sep_deg=None,
        ) == (True, None)
    for key in ("A_DMAX", "B_DMAX", "AP_DMAX", "BP_DMAX"):
        header[key] = 99.
        assert _SIP_KEY_REGEX.match(key)
        assert not WCS_REGEX.match(key)
    path = tmp_path / "sip.fits"
    _create_frame(path, header)

    for _ in range(3):
        _write_existing(path, accepted, writer)
        reread = fits.getheader(path)
        assert "A_3_0" not in reread
        assert ("A_ORDER" in reread) is new_sip
        assert ("B_ORDER" in reread) is new_sip
        assert all(reread[key] == 99. for key in ("A_DMAX", "B_DMAX", "AP_DMAX", "BP_DMAX"))
        reopened = WCS(reread)
        assert (reopened.sip is not None) is new_sip
        _assert_control(reopened, sip=new_sip)


def _create_lookup_frame(path, kind):
    old = _accepted_wcs()
    for axis, shift in ((1, 3.), (2, -4.)):
        table = DistortionLookupTable(
            np.full((4, 4), shift, dtype=np.float32), (1, 1), (1, 1), (21, 21),
        )
        setattr(old, f"{kind}{axis}", table)
    hdul = old.to_fits(relax=True)
    hdul[0].data = np.arange(SIDE**2, dtype=np.float32).reshape(SIDE, SIDE)
    hdul.writeto(path)


@pytest.mark.parametrize("writer", ["algorithm", "tool"])
@pytest.mark.parametrize("kind", ["det2im", "cpdis"])
def test_characterization_lookup_cards_can_reapply_old_detector_distortion(tmp_path, writer, kind):
    """BUG for D2IM: a clean accepted WCS reopens with the previous lookup map.

    The CPDIS case is the working cleanup control. Both use real lookup HDUs;
    the manual TAN calculation independently measures the surviving D2IM map.
    Header-only WCS construction hides the bug, as maintained tool readers do.
    """
    path = tmp_path / f"{kind}.fits"
    _create_lookup_frame(path, kind)
    accepted = _accepted_wcs()
    _assert_control(accepted)
    with fits.open(path) as hdul:
        pixels = hdul[0].data.copy()
        lookup_data = [hdu.data.copy() for hdu in hdul[1:]]
        old = WCS(hdul[0].header, hdul)
        # New candidate lookup maps are rejected, independently of write-back.
        assert _accept_solution(
            old, expected_parity=None, ra_hint_deg=None, dec_hint_deg=None,
            width=SIDE, height=SIDE, max_sep_deg=None,
        )[0] is False

    for _ in range(3):
        _write_existing(path, accepted, writer)
        with fits.open(path) as hdul:
            assert len(hdul) == 3
            np.testing.assert_array_equal(hdul[0].data, pixels)
            for hdu, original in zip(hdul[1:], lookup_data):
                np.testing.assert_array_equal(hdu.data, original)
            reopened = WCS(hdul[0].header, hdul)
            header_only = build_wcs_from_header(hdul[0].header)
            _assert_control(header_only)
            actual = reopened.pixel_to_world(PIXELS[:, 0], PIXELS[:, 1]).icrs
            if kind == "det2im":
                assert "D2IMDIS1" in hdul[0].header
                assert reopened.det2im1 is not None
                expected_old_map = _expected_icrs(detector_shift=(3., -4.))
                assert np.max(actual.separation(expected_old_map).arcsec) < 2e-7
                error = actual[-1].separation(_expected_icrs()[-1]).arcsec
                assert error == pytest.approx(5., abs=2e-7)
            else:
                assert "CPDIS1" not in hdul[0].header
                assert not any(key.startswith("DP1") for key in hdul[0].header)
                assert reopened.cpdis1 is None
                _assert_control(reopened)


def test_characterization_public_write_boundary_preserves_old_d2im(tmp_path, monkeypatch):
    """Real staged public write/read with a mocked solver, not a solver success."""
    path = tmp_path / "public-d2im.fits"
    _create_lookup_frame(path, "det2im")
    accepted = _accepted_wcs()
    calls = []

    def solver_seam(*args, **kwargs):
        calls.append(True)
        return WcsSolveResult(
            wcs=accepted, catalog_sources=(),
            metadata=WcsSolveMetadata(width_px=SIDE, height_px=SIDE),
        )

    monkeypatch.setattr(public_wcs, "_solve_wcs", solver_seam)
    monkeypatch.setattr(public_wcs, "_configured_backend_warnings", lambda settings: ([], []))
    summary = public_wcs.solve_astrometry(
        path, index_path=tmp_path, force=True, write_header=True,
    )
    assert calls == [True]
    assert not summary.errors
    assert summary.has_wcs is True
    assert summary.center_ra_deg == pytest.approx(120., abs=1e-10)
    assert summary.center_dec_deg == pytest.approx(20., abs=1e-10)
    with fits.open(path) as hdul:
        full = WCS(hdul[0].header, hdul)
        error = full.pixel_to_world(31.5, 31.5).icrs.separation(_expected_icrs()[-1]).arcsec
        assert error == pytest.approx(5., abs=2e-7)
    assert not list(tmp_path.glob(".public-d2im.fits.*"))
    # A later default call short-circuits using the header-only interpretation.
    later = public_wcs.solve_astrometry(path)
    assert calls == [True]
    assert later.center_ra_deg == pytest.approx(120., abs=1e-10)
    assert [warning.code for warning in later.warnings] == ["wcs_from_header"]


@pytest.mark.parametrize("writer", ["algorithm", "tool"])
def test_characterization_alternate_geometry_removed_but_ancillary_cards_survive(tmp_path, writer):
    accepted = _accepted_wcs()
    header = accepted.to_header()
    header.update(_accepted_wcs("FK4").to_header(key="A"))
    header["CNAME1"] = "Old coordinate label"
    path = tmp_path / "alternate.fits"
    _create_frame(path, header)
    _write_existing(path, accepted, writer)
    reread = fits.getheader(path)
    assert reread["EQUINOXA"] == 1950.
    assert reread["CNAME1"] == "Old coordinate label"
    assert not any(key in reread for key in ("CTYPE1A", "CRVAL1A", "RADESYSA", "CDELT1A"))
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*EQUINOXA.*", category=FITSFixedWarning)
        _assert_control(WCS(reread))
        # NAXIS permits a default linear alternate object, but its old
        # celestial coordinate system has been removed.
        assert WCS(reread, key="A").has_celestial is False


@pytest.mark.parametrize("writer", ["algorithm", "tool"])
def test_characterization_observation_time_preservation_differs_between_writers(tmp_path, writer):
    """Observation dates are independent metadata, not obsolete coordinate epochs.

    The algorithm explicitly restores the source time cards. The staged writer
    instead accepts conflicting time metadata carried by a supplied WCS. This
    conditional probe does not establish that a native backend emits those times.
    """
    accepted = _accepted_wcs()
    accepted.wcs.dateobs = "2020-01-02T03:04:05"
    accepted.wcs.mjdobs = 58850.1278356481
    accepted.wcs.dateref = "2020-01-01T06:00:00"
    accepted.wcs.mjdref = [58849., .25]
    source_times = {
        "DATE-OBS": "2026-01-02T03:04:05", "MJD-OBS": 61042.1278356481,
        "DATEREF": "2026-01-01T18:00:00", "MJDREFI": 61041., "MJDREFF": .75,
    }
    header = fits.Header([
        (key, value, "original observation") for key, value in source_times.items()
    ])
    path = tmp_path / "observation.fits"
    _create_frame(path, header)
    _write_existing(path, accepted, writer)
    reread = fits.getheader(path)
    expected = source_times if writer == "algorithm" else dict(accepted.to_header())
    for key in source_times:
        if isinstance(expected[key], str):
            assert reread[key] == expected[key]
        else:
            assert reread[key] == pytest.approx(expected[key], abs=1e-9)
        if writer == "algorithm":
            assert reread.comments[key] == "original observation"
    _assert_control(WCS(reread))


@pytest.mark.parametrize("writer", ["algorithm", "tool"])
def test_characterization_single_mjdref_is_overwritten_by_default_wcs(tmp_path, writer):
    """Both writers omit the single-card MJDREF form from explicit preservation."""
    accepted = _accepted_wcs()
    path = tmp_path / "mjdref.fits"
    _create_frame(path, fits.Header([("MJDREF", 61041.75, "observation time origin")]))
    _write_existing(path, accepted, writer)
    assert fits.getheader(path)["MJDREF"] == 0.


def test_algorithm_serialization_failure_mutates_header_but_staged_tool_preserves_file(tmp_path):
    """Failure-path characterization: only the file writer stages its rewrite."""
    class BrokenSerialization:
        def to_header(self, **kwargs):
            raise RuntimeError("characterization: cannot serialize solution")

    header = _accepted_wcs().to_header()
    with pytest.raises(RuntimeError, match="cannot serialize"):
        _write_wcs_to_header(header, BrokenSerialization())
    assert "CRVAL1" not in header
    assert "CTYPE1" not in header
    assert "WCS calibration applied" in str(header["HISTORY"])

    path = tmp_path / "atomic.fits"
    _create_lookup_frame(path, "det2im")
    original = path.read_bytes()
    with pytest.raises(RuntimeError, match="cannot serialize"):
        _write_existing(path, BrokenSerialization(), "tool")
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".atomic.fits.*"))
