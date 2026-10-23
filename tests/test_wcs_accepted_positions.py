"""M2 accepted positions and reference coverage; no native solvers/catalogs.

Only the backend boundary is replaced. Real Astropy WCS transformations drive
acceptance, header write-back and the catalog query/filtering below.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from astropy.coordinates import SkyCoord
from astropy.io import fits
from astropy.wcs import WCS, Sip

import algorithms.wcs.wcs as pipeline
from algorithms.skylib_lite.astrometry.atlas.config import AtlasConfig
from algorithms.skylib_lite.astrometry.types import SolveSolution
from algorithms.wcs.schemas import SourceExtractionData


WIDTH, HEIGHT = 1056, 1027


def _wcs(ra=150.0, dec=-30.0, scale=0.6):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [ra, dec]
    wcs.wcs.crpix = [(WIDTH + 1) / 2, (HEIGHT + 1) / 2]
    wcs.wcs.cd = np.diag([-scale / 3600, scale / 3600])
    return wcs


def _run(monkeypatch, tmp_path, solution, *, backend="anet", hint=(150.0, -30.0), scale=None,
         header_wcs=None):
    header = fits.Header({"NAXIS": 2, "NAXIS1": WIDTH, "NAXIS2": HEIGHT})
    if hint is not None:
        # Use an explicit hour-angle string: small numeric RA values have an
        # existing ambiguous hours/degrees heuristic, outside this checkpoint.
        header["RA"] = SkyCoord(*hint, unit="deg").ra.to_string(unit="hourangle", sep=":", precision=8)
        header["DEC"] = hint[1]
    if scale is not None:
        header["SECPIX"] = scale
    if header_wcs is not None:
        header.update(header_wcs.to_header(relax=True))
    before = header.copy()
    config = AtlasConfig(catalog_roots={"ucac5": tmp_path}) if backend == "atlas" else None
    monkeypatch.setattr(pipeline, "build_anet_config", lambda _: object() if backend == "anet" else None)
    monkeypatch.setattr(pipeline, "build_atlas_config", lambda _: config)
    monkeypatch.setattr(pipeline, "run_source_extraction", lambda *a, **kw: (
        [SourceExtractionData(x=10, y=20, flux=100)], None, None))
    monkeypatch.setattr(pipeline.AstrometryNetBackend, "is_available", lambda self: True)
    backend_type = pipeline.AstrometryNetBackend if backend == "anet" else pipeline.AtlasBackend
    monkeypatch.setattr(backend_type, "solve", lambda *a, **kw: SolveSolution(wcs=solution, backend=backend))
    result = pipeline.solve_wcs(header, np.zeros((HEIGHT, WIDTH), dtype=np.float32), tmp_path)
    return result, header, before


@pytest.mark.parametrize("backend", ["anet", "atlas"])
@pytest.mark.parametrize("scale", [None, 0.6])
def test_a_distant_narrow_solution_never_replaces_the_header(monkeypatch, tmp_path, backend, scale):
    result, header, before = _run(monkeypatch, tmp_path, _wcs(190), backend=backend, scale=scale)
    assert result.wcs is None
    assert header == before
    assert result.catalog_sources == ()
    if backend == "atlas":
        assert result.metadata.atlas_accepted is False


@pytest.mark.parametrize("hint", [(150.3, -30.0), None])
def test_a_nearby_or_unhinted_solution_is_accepted_without_a_scale_prior(monkeypatch, tmp_path, hint):
    result, header, _ = _run(monkeypatch, tmp_path, _wcs(), hint=hint)
    assert result.wcs is not None
    assert header["CTYPE1"] == "RA---TAN"
    assert result.metadata.ra_deg == pytest.approx(150)
    assert result.metadata.dec_deg == pytest.approx(-30)


@pytest.mark.parametrize("coordinate", [0, 1])
def test_a_nonfinite_solution_is_rejected_even_without_a_hint(monkeypatch, tmp_path, coordinate):
    solution = _wcs()
    crval = solution.wcs.crval.copy()
    crval[coordinate] = float("nan")
    solution.wcs.crval = crval
    result, header, before = _run(monkeypatch, tmp_path, solution, hint=None)
    assert result.wcs is None
    assert header == before


@pytest.mark.parametrize("frame,equinox", [("FK4", 1900.0), ("FK5", 1800.0)])
@pytest.mark.parametrize("solution_frame", ["native", "icrs"])
def test_header_wcs_hints_and_solutions_are_compared_in_icrs(
    monkeypatch, tmp_path, frame, equinox, solution_frame,
):
    original = _wcs(0, 0)
    original.wcs.radesys, original.wcs.equinox = frame, equinox
    center = original.pixel_to_world((WIDTH - 1) / 2, (HEIGHT - 1) / 2).icrs
    solution = original if solution_frame == "native" else _wcs(center.ra.deg, center.dec.deg)
    result, _, _ = _run(monkeypatch, tmp_path, solution, hint=None, header_wcs=original)
    assert result.wcs is not None
    assert result.metadata.search_center_ra_deg == pytest.approx(center.ra.deg, abs=1e-10)
    assert result.metadata.search_center_dec_deg == pytest.approx(center.dec.deg, abs=1e-10)
    assert result.metadata.ra_deg == pytest.approx(center.ra.deg, abs=1e-10)
    assert result.metadata.dec_deg == pytest.approx(center.dec.deg, abs=1e-10)


@pytest.mark.parametrize("ra,dec", [(150, -30), (359.98, 20), (30, 89.95), (30, -89.95)])
def test_atlas_references_cover_the_solved_field_not_the_hint_or_search_scale(
    monkeypatch, tmp_path, ra, dec,
):
    solution = _wcs(ra, dec)
    # A rotated/sheared image with CRPIX away from its centre. Neither CRVAL
    # nor a mean pixel scale describes the full detector footprint.
    solution.wcs.crpix = [100, 200]
    solution.wcs.cd = np.array([[-0.5, 0.35], [0.2, 0.8]]) / 3600
    pixels = np.array([[0, 0], [WIDTH - 1, 0], [0, HEIGHT - 1],
                       [WIDTH - 1, HEIGHT - 1], [(WIDTH - 1) / 2, (HEIGHT - 1) / 2]])
    stars = solution.pixel_to_world(pixels[:, 0], pixels[:, 1]).icrs
    queries = []

    def query_box(ra_min, ra_max, dec_min, dec_max, **kwargs):
        queries.append((ra_min, ra_max, dec_min, dec_max))
        # Match UCAC's wrapped, inclusive intervals, including the RA seam.
        lo, hi = ra_min % 360, ra_max % 360
        in_ra = ((stars.ra.deg >= lo) & (stars.ra.deg <= hi) if lo <= hi else
                 (stars.ra.deg >= lo) | (stars.ra.deg <= hi))
        keep = in_ra & (stars.dec.deg >= dec_min) & (stars.dec.deg <= dec_max)
        return SimpleNamespace(ra_deg=stars.ra.deg[keep], dec_deg=stars.dec.deg[keep])

    monkeypatch.setattr(pipeline, "get_catalog_spec", lambda _: SimpleNamespace(
        index_factory=lambda _: SimpleNamespace(query_box=query_box)))
    center = solution.pixel_to_world((WIDTH - 1) / 2, (HEIGHT - 1) / 2).icrs
    result, _, _ = _run(monkeypatch, tmp_path, solution, backend="atlas",
                         hint=(float(center.ra.deg + 0.3) % 360, float(center.dec.deg)))
    assert result.wcs is not None, result.metadata.solver_failures
    assert queries
    # The old 60 arcsec/pixel requery violates the two-degree catalog budget;
    # a query derived from this solved sub-degree field must fit it.
    references = SkyCoord([s.ra_hours * 15 for s in result.catalog_sources],
                          [s.dec_degs for s in result.catalog_sources], unit="deg")
    assert len(references) >= len(stars)
    assert np.all(stars.match_to_catalog_sky(references)[1].arcsec < 1e-6)


def test_the_solved_reference_footprint_keeps_the_preload_budget(monkeypatch, tmp_path):
    solution = _wcs(scale=20)
    monkeypatch.setattr(pipeline, "get_catalog_spec", lambda _: pytest.fail("oversized footprint loaded a catalog"))
    result, header, before = _run(monkeypatch, tmp_path, solution, backend="atlas")
    assert result.wcs is None
    assert header == before
    assert any("footprint" in reason for reason in result.metadata.solver_failures)


def test_reference_footprint_includes_a_distorted_edge_between_corners(monkeypatch, tmp_path):
    solution = _wcs()
    solution.wcs.ctype = ["RA---TAN-SIP", "DEC--TAN-SIP"]
    # y displacement peaks at the middle of the lower edge and vanishes at
    # its corners. A corners-only footprint would omit that edge's stars.
    a, b = np.zeros((5, 5)), np.zeros((5, 5))
    half_width = WIDTH / 2
    b[0, 2] = 0.008
    b[2, 2] = -0.008 / half_width**2
    solution.sip = Sip(a, b, None, None, solution.wcs.crpix)
    edge = solution.pixel_to_world((WIDTH - 1) / 2, 0).icrs
    calls = []

    def query_box(lo, hi, bottom, top, **kwargs):
        calls.append((lo, hi, bottom, top))
        keep = bottom <= edge.dec.deg <= top
        return SimpleNamespace(ra_deg=np.array([edge.ra.deg]) if keep else np.array([]),
                               dec_deg=np.array([edge.dec.deg]) if keep else np.array([]))

    monkeypatch.setattr(pipeline, "get_catalog_spec", lambda _: SimpleNamespace(
        index_factory=lambda _: SimpleNamespace(query_box=query_box)))
    result, _, _ = _run(monkeypatch, tmp_path, solution, backend="atlas")
    assert result.wcs is not None, result.metadata.solver_failures
    assert calls
    assert len(result.catalog_sources) == 1


def test_split_polar_queries_share_the_returned_row_budget(monkeypatch, tmp_path):
    from algorithms.skylib_lite.astrometry.atlas.catalog import limits

    monkeypatch.setattr(limits, "MAX_QUERY_ROWS", 3)

    def query_box(lo, hi, *args, **kwargs):
        return SimpleNamespace(ra_deg=np.array([lo, lo + 90]), dec_deg=np.array([89.99, 89.99]))

    monkeypatch.setattr(pipeline, "get_catalog_spec", lambda _: SimpleNamespace(
        index_factory=lambda _: SimpleNamespace(query_box=query_box)))
    with pytest.raises(ValueError, match="budget"):
        pipeline._load_atlas_catalog_sources(
            AtlasConfig(catalog_roots={"ucac5": tmp_path}), wcs_obj=_wcs(30, 89.99),
            width=WIDTH, height=HEIGHT, file_id=None)
