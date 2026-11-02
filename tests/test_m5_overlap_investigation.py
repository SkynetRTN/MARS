"""PHOT-19 correctness regressions for exact ellipse/pixel overlaps.

Independent oracles use analytic geometry and quadrature, without calling SEP. The pinned
SEP 1.4.1 source was separately fetched and compiled for this investigation:
https://github.com/sep-developers/sep/blob/v1.4.1/src/overlap.h#L475-L502
It retains both third-edge intersections; the Python port discarded the second
and averaged the first with the stale prior-edge sentinel (2, 2).
The official C implementation agrees with the half-disk and ellipse-cap oracles.
Routine tests require neither downloads nor compiled upstream source.

All potentially fatal geometry executes in a bounded child interpreter with
native JIT enabled. The >=0.5-pixel production guard remains active.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Native overlap probes use POSIX resource limits")


@pytest.fixture(scope="module")
def native_env(tmp_path_factory):
    return {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "NUMBA_DISABLE_JIT": "0",
        "NUMBA_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "NUMBA_CACHE_DIR": str(tmp_path_factory.mktemp("m5_overlap_numba_cache")),
    }


def _run_probe(source: str, native_env) -> subprocess.CompletedProcess[str]:
    setup = "import resource\nresource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n"
    return subprocess.run(
        [sys.executable, "-c", setup + textwrap.dedent(source)],
        cwd=REPO_ROOT,
        env=native_env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.slow
def test_phot19_triangle_overlap_recovers_a_half_unit_disk(native_env):
    """The triangle contains exactly the upper half of the unit disk."""
    result = _run_probe("""
        import json
        import numpy as np
        from algorithms.skylib_lite.util.overlap import triangle_unitcircle_overlap
        vertices = np.array([[1.2, 0.], [1.2, 2.], [-3., 0.]])
        areas = []
        for transform in (np.eye(2), np.diag([-1., 1.]),
                          np.array([[0., -1.], [1., 0.]])):
            triangle = vertices @ transform.T
            areas.append(triangle_unitcircle_overlap(*triangle.ravel()))
        print(json.dumps(areas))
    """, native_env)
    assert result.returncode == 0, result
    assert json.loads(result.stdout) == pytest.approx([math.pi / 2] * 3, abs=1e-13)


@pytest.mark.slow
def test_phot19_public_ellipse_weights_a_cap_by_its_exact_area(native_env):
    """A unit impulse in the left cap should weigh 0.3070924246521893."""
    result = _run_probe("""
        import json
        import numpy as np
        from astropy.io.fits import Header
        from algorithms.photometry.photometry import run_photometry
        from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData
        from algorithms.skylib_lite.photometry.aperture_numba import sum_ellipse
        image = np.zeros((11, 11), dtype=np.float64)
        image[5, 4] = 1.
        measured = sum_ellipse(image, 5., 5., 1., .5, 0.)
        rows = run_photometry(
            image, Header({"EXPTIME": 1.}), [SourceExtractionData(x=6., y=6.)],
            PhotometrySettings(a=1., b=.5, theta=0., apcorr_tol=0.),
            background=np.zeros_like(image), background_rms=np.ones_like(image),
        )
        print(json.dumps({"flux": rows[0].flux, "count": len(rows),
                          "kernel_flux": float(measured[0][0]),
                          "kernel_flag": int(measured[3][0])}))
    """, native_env)
    assert result.returncode == 0, result
    row = json.loads(result.stdout)
    # Ellipse is unit circle scaled by b=.5; this is the circle cap x <= -.5.
    expected = .5 * (math.acos(.5) - .5 * math.sqrt(1 - .5**2))
    assert expected == pytest.approx(.3070924246521893, abs=1e-15)
    assert row["count"] == 1
    assert row["kernel_flag"] == 0
    assert row["flux"] == pytest.approx(expected, abs=1e-12)
    assert row["kernel_flux"] == row["flux"]


@pytest.mark.slow
def test_phot19_public_ellipse_recovers_area_at_the_retained_axis_floor(native_env):
    """The former native crash and its symmetries recover pi*a*b."""
    result = _run_probe("""
        import json
        import numpy as np
        from astropy.io.fits import Header
        from algorithms.photometry.photometry import run_photometry
        from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData
        image = np.ones((11, 11), dtype=np.float64)
        fluxes = []
        for x, y, theta in ((5.5, 6.2, -45.), (6.5, 6.2, 45.),
                            (5.8, 5.5, 45.), (6.2, 6.5, 45.)):
            rows = run_photometry(
                image, Header({"EXPTIME": 1.}), [SourceExtractionData(x=x, y=y)],
                PhotometrySettings(a=.8, b=.5, theta=theta, apcorr_tol=0.),
                background=np.zeros_like(image), background_rms=np.ones_like(image),
            )
            fluxes.append(rows[0].flux)
        print(json.dumps(fluxes))
    """, native_env)
    assert result.returncode == 0, result
    assert json.loads(result.stdout) == pytest.approx([math.pi * .8 * .5] * 4, abs=1e-12)


@pytest.mark.slow
def test_phot19_adversarial_pixels_match_independent_ellipse_integrals(native_env):
    """Check individual weights, so compensating errors cannot hide in the sum.

    These four pixels tile the .8 x .5 ellipse at theta=-pi/4 from the former
    public crash. Its equation is (89/32)*(x*x + y*y) + (39/16)*x*y <= 1.
    The literal areas were computed independently by integrating the vertical
    interval between its quadratic roots, clipped to each rectangle. Reflection
    and quarter-turns must preserve each area.
    """
    result = _run_probe("""
        import json
        import math
        from algorithms.skylib_lite.util.overlap import ellipoverlap
        areas = []
        for xmin, ymin, xmax, ymax in ((-1., -.7, 0., .3), (0., -.7, 1., .3),
                                      (-1., .3, 0., 1.3), (0., .3, 1., 1.3)):
            areas.append([
                ellipoverlap(xmin, ymin, xmax, ymax, .8, .5, -math.pi/4),
                ellipoverlap(-xmax, ymin, -xmin, ymax, .8, .5, math.pi/4),
                ellipoverlap(-ymax, xmin, -ymin, xmax, .8, .5, math.pi/4),
            ])
        print(json.dumps(areas))
    """, native_env)
    assert result.returncode == 0, result
    expected = (.41678408543945455, .5587849616353734,
                .21153444527850623, .06953356908258775)
    for variants, area in zip(json.loads(result.stdout), expected, strict=True):
        assert variants == pytest.approx([area] * 3, abs=1e-12)
