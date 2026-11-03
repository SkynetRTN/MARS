"""M5 solver-control evidence; characterization only, no production fixes.

The default probes write/read actual xylist FITS tables and run real wrapper/
backend control flow with deterministic solver seams. An explicitly enabled
native probe checks astrometry.net's parity convention using index-derived
points, without claiming independent real-image recovery. WCS handedness is
also checked using oriented sky offsets and a reflected-pixel correspondence.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
from types import SimpleNamespace

import numpy as np
import pytest
from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS

import algorithms.wcs.wcs as pipeline
import algorithms.skylib_lite.astrometry.atlas.backend as atlas_module
from algorithms.skylib_lite.astrometry.anet.backend import AstrometryNetBackend
from algorithms.skylib_lite.astrometry.atlas.backend import AtlasBackend
from algorithms.skylib_lite.astrometry.atlas.config import AtlasConfig
from algorithms.skylib_lite.astrometry.atlas.solve.oriented import _known_cd_rad_per_pix
from algorithms.skylib_lite.astrometry.types import SolveRequest, SolveSolution
from algorithms.wcs.config import SolverSettings, WcsSearchBounds
from algorithms.wcs.schemas import (
    PlateSolveSettings,
    SourceExtractionData,
    WcsCalibrationSettings,
)


WIDTH, HEIGHT = 64, 48


def _solution(positive: bool) -> WCS:
    angle = np.deg2rad(23)
    rotation = np.array([[np.cos(angle), -np.sin(angle)],
                         [np.sin(angle), np.cos(angle)]])
    result = WCS(naxis=2)
    result.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    result.wcs.crval = [120, 30]
    result.wcs.crpix = [(WIDTH + 1) / 2, (HEIGHT + 1) / 2]
    result.wcs.cd = rotation @ np.diag([1 if positive else -1, 1]) / 3600
    return result


def _header(kind: str) -> fits.Header:
    header = fits.PrimaryHDU(np.zeros((HEIGHT, WIDTH), dtype=np.float32)).header
    if kind in ("positive", "negative"):
        header.update(_solution(kind == "positive").to_header())
    elif kind == "pointing":
        header["OBJRA"] = 8.0
        header["OBJDEC"] = 30.0
    return header


def _sources(fluxes):
    return [SourceExtractionData(x=float(i + 1), y=10, flux=flux)
            for i, flux in enumerate(fluxes)]


def _capture_anet(monkeypatch, tmp_path, sources, candidate=None):
    """Keep actual xylist writer/command; replace only the native search."""
    captured = []
    monkeypatch.setattr(pipeline, "run_source_extraction",
                        lambda *a, **kw: (sources, None, None))
    monkeypatch.setattr(AstrometryNetBackend, "is_available", lambda *a: True)

    def search(request, config):
        path = AstrometryNetBackend._write_xylist(request, tmp_path)
        command = AstrometryNetBackend()._build_cmd(
            "solve-field", path, "solved", tmp_path, tmp_path / "engine.cfg",
            request, use_hint=True,
        )
        captured.append((request, Table.read(path), command))
        return SolveSolution(wcs=candidate, backend="an")

    monkeypatch.setattr(pipeline, "anet_solve_field_glob", search)
    return captured


def _run(tmp_path, header, **kwargs):
    return pipeline.solve_wcs(
        header, np.zeros((HEIGHT, WIDTH), dtype=np.float32), tmp_path, **kwargs,
    )


def test_handedness_oracle_uses_sky_offsets_and_reflected_pixels():
    """A reflected input gives identical sky positions at reflected pixels."""
    positive, negative = _solution(True), _solution(False)
    points = np.array([[5, 6], [31.5, 23.5], [55, 39]], dtype=float)
    reflected = points.copy()
    reflected[:, 0] = WIDTH - 1 - reflected[:, 0]
    assert np.max(positive.pixel_to_world(*points.T).separation(
        negative.pixel_to_world(*reflected.T)).arcsec) < 1e-7
    for wcs, expected_sign in ((positive, 1), (negative, -1)):
        origin = wcs.pixel_to_world(31.5, 23.5)
        dx = origin.spherical_offsets_to(wcs.pixel_to_world(32.5, 23.5))
        dy = origin.spherical_offsets_to(wcs.pixel_to_world(31.5, 24.5))
        oriented_area = dx[0].arcsec * dy[1].arcsec - dx[1].arcsec * dy[0].arcsec
        assert np.sign(oriented_area) == expected_sign
        assert np.sign(np.linalg.det(wcs.pixel_scale_matrix)) == expected_sign


@pytest.mark.parametrize("header_kind", ["positive", "negative", "pointing", "none"])
@pytest.mark.parametrize("candidate_positive", [False, True])
@pytest.mark.parametrize("backend", ["anet", "atlas"])
def test_automatic_parity_request_command_and_acceptance(
    monkeypatch, tmp_path, header_kind, candidate_positive, backend,
):
    """Automatic hints constrain a determinant; pointing alone does not."""
    candidate = _solution(candidate_positive)
    captured = _capture_anet(
        monkeypatch, tmp_path, _sources([3, 2, 1]),
        candidate=candidate if backend == "anet" else None,
    )
    atlas_calls = []

    def blind_search(path, config, **kwargs):
        atlas_calls.append(kwargs)
        return SimpleNamespace(wcs=candidate,
                               metadata={"n_sources_extracted": 137, "n_sources": 17})

    monkeypatch.setattr(atlas_module, "atlas_solve", blind_search)
    monkeypatch.setattr(pipeline, "_load_atlas_catalog_sources", lambda *a, **kw: [])
    requests = []

    class CapturedAtlasBackend(AtlasBackend):
        def solve(self, request, config):
            requests.append(request)
            return super().solve(request, config)

    monkeypatch.setattr(pipeline, "AtlasBackend", CapturedAtlasBackend)
    settings = SolverSettings(
        anet_index_path="unused" if backend == "anet" else None,
        atlas_catalog_root="unused" if backend == "atlas" else None,
    )
    result = _run(tmp_path, _header(header_kind), solver_settings=settings)
    expected = {"positive": True, "negative": False}.get(header_kind)
    should_accept = expected is None or expected == candidate_positive
    if backend == "anet":
        request, table, command = captured[0]
        assert request.parity is (None if expected is None else not expected)
        assert len(table) == 3
        if expected is None:
            assert "--parity" not in command
        else:
            assert command[command.index("--parity") + 1] == ("neg" if expected else "pos")
        # All-sky defaults omit the pointing CLI arguments even with a hint.
        assert "--ra" not in command
    elif header_kind == "none":
        assert requests == atlas_calls == []
        assert result.metadata.atlas_failure_reason == "no_pointing_hint"
        should_accept = False
    else:
        assert len(requests) == len(atlas_calls) == 1
        assert requests[0].parity is expected
        assert requests[0].rotation_deg is None
        assert "parity" not in atlas_calls[0]
        assert result.metadata.atlas_source_count == 137
        assert result.metadata.atlas_accepted is should_accept
    assert (result.wcs is not None) is should_accept


def test_maintained_preferences_do_not_expose_explicit_parity_or_source_cap():
    assert WcsCalibrationSettings().parity is None
    assert WcsCalibrationSettings().max_sources == 100
    assert not {"parity", "max_sources"} & PlateSolveSettings.model_fields.keys()
    assert not {"parity", "max_sources"} & WcsSearchBounds.__dataclass_fields__.keys()


@pytest.mark.parametrize("parity", [False, True])
@pytest.mark.parametrize("header_kind", ["positive", "pointing"])
def test_explicit_parity_is_a_latent_anet_flag_and_does_not_override_acceptance(
    monkeypatch, tmp_path, parity, header_kind,
):
    """A test-only settings factory is required to enter the explicit branch.

    The candidate's sign is controlled independently of the request: this test
    proves plumbing and header-derived acceptance, not native solve-field parity.
    """
    candidate = _solution(False)
    captured = _capture_anet(monkeypatch, tmp_path, _sources([1]), candidate)
    monkeypatch.setattr(pipeline, "WcsCalibrationSettings",
                        lambda: WcsCalibrationSettings(parity=parity))
    result = _run(tmp_path, _header(header_kind),
                  solver_settings=SolverSettings(anet_index_path="unused"))
    request, _, command = captured[0]
    assert request.parity is parity
    assert command[command.index("--parity") + 1] == ("pos" if parity else "neg")
    assert (result.wcs is not None) is (header_kind == "pointing")


@pytest.mark.parametrize("parity", [None, False, True])
def test_atlas_blind_search_ignores_explicit_parity_but_echoes_it(
    monkeypatch, tmp_path, parity,
):
    observed = []
    candidate = _solution(True)

    def search(path, config, **kwargs):
        observed.append(kwargs)
        return SimpleNamespace(wcs=candidate, metadata={"n_sources_extracted": 9})

    monkeypatch.setattr(atlas_module, "atlas_solve", search)
    request = SolveRequest(image_path=tmp_path / "unused.fits", parity=parity,
                           ra_hours=8, dec_degs=30, max_sources=2)
    result = AtlasBackend().solve(request, AtlasConfig())
    assert len(observed) == 1
    assert "parity" not in observed[0]
    assert "max_sources" not in observed[0]
    assert result.wcs is candidate
    assert result.attempt.method == "blind"
    assert result.attempt.parity is parity
    assert result.attempt.max_sources == 2
    assert result.source_count == 9


@pytest.mark.parametrize("parity", [False, True])
@pytest.mark.parametrize("header_kind", ["positive", "pointing"])
def test_latent_explicit_atlas_request_does_not_override_header_acceptance(
    monkeypatch, tmp_path, parity, header_kind,
):
    observed = []
    monkeypatch.setattr(pipeline, "run_source_extraction",
                        lambda *a, **kw: ([], None, None))
    monkeypatch.setattr(pipeline, "WcsCalibrationSettings",
                        lambda: WcsCalibrationSettings(parity=parity))
    monkeypatch.setattr(pipeline, "_load_atlas_catalog_sources", lambda *a, **kw: [])

    class CapturedAtlasBackend(AtlasBackend):
        def solve(self, request, config):
            observed.append(request)
            return super().solve(request, config)

    monkeypatch.setattr(pipeline, "AtlasBackend", CapturedAtlasBackend)
    monkeypatch.setattr(
        atlas_module, "atlas_solve",
        lambda *a, **kw: SimpleNamespace(wcs=_solution(False), metadata={}),
    )
    result = _run(tmp_path, _header(header_kind),
                  solver_settings=SolverSettings(atlas_catalog_root="unused"))
    assert observed[0].parity is parity
    assert observed[0].rotation_deg is None
    assert (result.wcs is not None) is (header_kind == "pointing")


@pytest.mark.parametrize("parity,sign", [(None, 1), (False, -1), (True, 1)])
def test_atlas_oriented_path_uses_determinant_sign(monkeypatch, tmp_path, parity, sign):
    observed = []

    def search(path, config, **kwargs):
        observed.append(kwargs)
        return SimpleNamespace(wcs=_solution(sign > 0), metadata={"n_sources": 8})

    monkeypatch.setattr(atlas_module, "solve_oriented", search)
    request = SolveRequest(image_path=tmp_path / "unused.fits", parity=parity,
                           rotation_deg=23, min_scale=1, max_scale=1,
                           ra_hours=8, dec_degs=30)
    result = AtlasBackend().solve(request, AtlasConfig())
    assert observed[0]["parity_sign"] == sign
    assert np.sign(np.linalg.det(result.wcs.pixel_scale_matrix)) == sign
    assert result.attempt.method == "oriented"


@pytest.mark.parametrize("sign", [-1, 1])
def test_actual_oriented_cd_agrees_with_independent_sky_reflection(sign):
    matrix = _known_cd_rad_per_pix(1, 23, sign)
    independent_wcs = _solution(sign > 0)
    np.testing.assert_allclose(matrix, np.deg2rad(independent_wcs.pixel_scale_matrix),
                               rtol=1e-14, atol=1e-20)
    assert np.sign(np.linalg.det(matrix)) == sign


@pytest.mark.parametrize(
    "flux,expected_x,expected_flux",
    [
        (None, [1, 2, 3, 4], None),
        ([10, 40, 20, 30], [2, 4], [40, 30]),
        ([10, np.nan, np.inf, -np.inf], [2, 3], [np.nan, np.inf]),
    ],
    ids=["missing-flux-ignores-cap", "finite-brightest-cap", "nonfinite-kept-first"],
)
def test_actual_xylist_source_cap_depends_on_flux(tmp_path, flux, expected_x, expected_flux):
    request = SolveRequest(xy=np.column_stack((np.arange(1, 5), np.ones(4))),
                           flux=flux, max_sources=2)
    table = Table.read(AstrometryNetBackend._write_xylist(request, tmp_path))
    assert list(table["X"]) == expected_x
    if expected_flux is None:
        assert table.colnames == ["X", "Y"]
    else:
        # FITS table readers mask NaN values; inspect the underlying FITS vector.
        raw = fits.getdata(tmp_path / "field.xyls", 1)["FLUX"]
        np.testing.assert_equal(raw, expected_flux)


def test_actual_xylist_partial_flux_vector_is_rejected(tmp_path):
    request = SolveRequest(xy=np.ones((4, 2)), flux=np.ones(3), max_sources=2)
    with pytest.raises(ValueError, match="flux must match xy length"):
        AstrometryNetBackend._write_xylist(request, tmp_path)
    assert not (tmp_path / "field.xyls").exists()


@pytest.mark.parametrize("kind", ["none", "partial", "finite", "nonfinite"])
def test_wrapper_cap_precedes_missing_or_nonfinite_flux_vector(
    monkeypatch, tmp_path, kind,
):
    if kind == "none":
        fluxes = [None] * 120
    elif kind == "partial":
        # With nonpositive peers, the missing value stays inside the top 100.
        fluxes = [999, None] + [0] * 118
    elif kind == "nonfinite":
        fluxes = [np.nan, np.inf] + list(range(118))
    else:
        fluxes = list(range(120))
    captured = _capture_anet(monkeypatch, tmp_path, _sources(fluxes))
    result = _run(tmp_path, _header("none"),
                  solver_settings=SolverSettings(anet_index_path="unused"))
    request, table, command = captured[0]
    assert request.max_sources == 100
    assert len(request.xy) == len(table) == result.metadata.n_field == 100
    if kind in ("none", "partial"):
        assert request.flux is None
        assert table.colnames == ["X", "Y"]
        assert "--sort-column" not in command
        np.testing.assert_array_equal(table["X"], np.arange(1, 101))
    else:
        assert request.flux is not None
        assert "--sort-column" in command
        if kind == "finite":
            np.testing.assert_array_equal(table["X"], np.arange(120, 20, -1))
        else:
            assert np.isnan(request.flux).any()
            assert np.isposinf(request.flux).any()
            assert list(table["X"][:2]) == [1, 2]


@pytest.mark.parametrize("bad_flux", [None, "bad", np.nan, np.inf])
def test_wrapper_flux_sanitization_is_presence_and_conversion_only(
    monkeypatch, tmp_path, bad_flux,
):
    sources = _sources([10, 20, 30])
    # Normal source-model construction cannot produce a string; this injects a
    # duck-typed input to exercise the wrapper's defensive float conversion.
    sources[1] = SourceExtractionData.model_construct(x=2, y=10, flux=bad_flux)
    captured = _capture_anet(monkeypatch, tmp_path, sources)
    _run(tmp_path, _header("none"),
         solver_settings=SolverSettings(anet_index_path="unused"))
    request, table, _ = captured[0]
    assert len(table) == 3
    if bad_flux is None or isinstance(bad_flux, str):
        assert request.flux is None
        assert table.colnames == ["X", "Y"]
    else:
        assert request.flux is not None
        assert not np.isfinite(request.flux[1])
        assert list(table["X"])[0] == 2


def test_wrapper_field_count_is_capped_rows_before_missing_position_filter(
    monkeypatch, tmp_path,
):
    sources = _sources([None] * 120)
    sources[0].x = None
    captured = _capture_anet(monkeypatch, tmp_path, sources)
    result = _run(tmp_path, _header("none"),
                  solver_settings=SolverSettings(anet_index_path="unused"))
    request, table, _ = captured[0]
    assert result.metadata.n_field == 100
    assert len(request.xy) == len(table) == 99
    np.testing.assert_array_equal(table["X"], np.arange(2, 101))


@pytest.mark.solver_data
@pytest.mark.parametrize("truth_positive", [False, True])
@pytest.mark.parametrize("request_parity", [False, True])
def test_native_anet_parity_on_exact_index_derived_field(
    tmp_path, truth_positive, request_parity,
):
    """Opt-in native convention check, not an independent real-image recovery.

    Set MARS_M5_NATIVE_PARITY_INDEX to a local ucac5-index-00-00.fits.
    The input uses that index's own star coordinates. A single index, two CPU
    seconds and an eight-second process-group wall limit keep each call bounded.
    No catalog or generated data is downloaded or committed.
    """
    configured_index = os.environ.get("MARS_M5_NATIVE_PARITY_INDEX")
    if not configured_index:
        pytest.skip("set MARS_M5_NATIVE_PARITY_INDEX to a local ucac5-index-00-00.fits")
    solve_field = shutil.which("solve-field")
    if solve_field is None:
        pytest.skip("native solve-field is unavailable")
    index = Path(configured_index).resolve()
    if not index.is_file():
        pytest.skip("configured native parity index is unavailable")
    if os.name != "posix":
        pytest.skip("native parity probe requires POSIX process-group termination")

    with fits.open(index, memmap=True) as hdus:
        stars = hdus[-1].data
        keep = ((abs(stars["RA_GAIA"] - 26) < .3)
                & (abs(stars["DEC_GAIA"] - 16.5) < .3))
        ra = np.asarray(stars["RA_GAIA"][keep])
        dec = np.asarray(stars["DEC_GAIA"][keep])
        magnitude = np.asarray(stars["GMAG"][keep])
    truth = WCS(naxis=2)
    truth.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    truth.wcs.crval = [26, 16.5]
    truth.wcs.crpix = [512.5, 512.5]
    truth.wcs.cd = np.diag([1 if truth_positive else -1, 1]) / 3600
    xy = np.column_stack(truth.all_world2pix(ra, dec, 1))
    inside = ((xy >= 1) & (xy <= 1024)).all(axis=1)
    xy = xy[inside]
    flux = 10 ** (-.4 * magnitude[inside])
    assert len(xy) >= 20, "the supplied index does not cover the fixed control field"
    request = SolveRequest(
        xy=xy, flux=flux, width=1024, height=1024,
        ra_hours=26 / 15, dec_degs=16.5, radius=.1,
        min_scale=.99, max_scale=1.01, parity=request_parity,
        sip_order=0, max_sources=100, retry_lost=False,
    )
    config = tmp_path / "engine.cfg"
    config.write_text(f"index {index}\n", encoding="ascii")
    source = AstrometryNetBackend._write_xylist(request, tmp_path)
    command = AstrometryNetBackend()._build_cmd(
        solve_field, source, "solved", tmp_path, config, request,
        use_hint=True, cpulimit=2,
    )
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        pytest.fail("native parity probe exceeded its eight-second wall limit")
    assert process.returncode == 0, output
    solved_path = tmp_path / "solved.wcs"
    assert solved_path.exists() is (request_parity != truth_positive), output
    if solved_path.exists():
        # Native .wcs files have NAXIS=0, hence Astropy's harmless image-axis
        # warning; the WCS itself supplies the two celestial axes under test.
        solved = WCS(fits.getheader(solved_path))
        assert (np.linalg.det(solved.pixel_scale_matrix) > 0) == truth_positive
        assert solved.pixel_to_world(511.5, 511.5).separation(
            truth.pixel_to_world(511.5, 511.5)).arcsec < 1
