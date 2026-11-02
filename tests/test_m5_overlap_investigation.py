"""PHOT-19 characterization: passing tests pin defects, not acceptance.

Independent oracles use closed-form geometry, without calling SEP. The pinned
SEP 1.4.1 source was separately fetched and compiled for this investigation:
https://github.com/sep-developers/sep/blob/v1.4.1/src/overlap.h#L475-L502
It retains both third-edge intersections; overlap.py:348 discards the second
and overlap.py:350-351 averages the first with stale prior-edge sentinel (2, 2).
The official C implementation agrees with both geometric area oracles below.
Routine tests require neither downloads nor compiled upstream source.

All potentially fatal geometry executes in a bounded child interpreter with
native JIT enabled. The >=0.5-pixel production guard remains active.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import textwrap

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Native crash probes use POSIX resource limits/signals")


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
def test_phot19_triangle_overlap_preserves_zero_for_a_half_unit_disk(native_env):
    """The triangle contains exactly the upper half of the unit disk."""
    result = _run_probe("""
        import json
        from algorithms.skylib_lite.util.overlap import triangle_unitcircle_overlap
        print(json.dumps({"area": triangle_unitcircle_overlap(1.2, 0., 1.2, 2., -3., 0.)}))
    """, native_env)
    assert result.returncode == 0, result
    measured = json.loads(result.stdout)["area"]
    expected = math.pi / 2
    assert measured == 0.0  # Current defect; do not treat as correct geometry.
    assert abs(measured - expected) == pytest.approx(expected, abs=1e-14)


@pytest.mark.slow
def test_phot19_public_ellipse_preserves_wrong_weight_with_no_flag(native_env):
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
    assert row["flux"] == pytest.approx(.7697455471792329, abs=1e-12)
    assert row["kernel_flux"] == row["flux"]
    assert row["flux"] / expected == pytest.approx(2.5065598672811333, rel=1e-12)


@pytest.mark.slow
def test_phot19_public_ellipse_crashes_with_axes_that_pass_the_guard(native_env):
    """New reachability: both axes meet the retained 0.5-pixel floor."""
    result = _run_probe("""
        import numpy as np
        from astropy.io.fits import Header
        from algorithms.photometry.photometry import run_photometry
        from algorithms.photometry.schemas import PhotometrySettings, SourceExtractionData
        image = np.ones((11, 11), dtype=np.float64)
        print("READY", flush=True)
        run_photometry(
            image, Header({"EXPTIME": 1.}), [SourceExtractionData(x=5.5, y=6.2)],
            PhotometrySettings(a=.8, b=.5, theta=-45., apcorr_tol=0.),
            background=np.zeros_like(image), background_rms=np.ones_like(image),
        )
        print("SURVIVED", flush=True)
    """, native_env)
    assert result.stdout == "READY\n", result
    assert result.stderr == "", result
    assert result.returncode == -signal.SIGSEGV, result
