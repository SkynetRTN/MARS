"""
algorithms.hrdiagram_py.hrfit - an Astromancer-faithful toolkit for turning a
photometry CSV into a well-fitted colour-magnitude / HR diagram of a star
cluster.

This is a deliberate parity *port*, not a byte-preserving extraction. It
retains the historical ``hrdiagram_py`` package name after the intermediate
TypeScript extraction at ``git-history:algorithms/hrdiagram`` retired. The
CM<->HR transform, extinction model, and sign conventions are lifted from the
Astromancer "cluster" tool
(``isochrone-plot.util.ts::computePlotDelta`` and
``cluster.util.ts::getExtinction``). Differences from Astromancer are noted in
comments so you can trace parity; two are permanent, deliberate deviations
rather than upstream defects reproduced for parity:

    - ``get_extinction`` uses ``rv`` throughout instead of Astromancer's
      hard-coded 3.1 leading factor (its extraction defect #1).
    - ``isochrone_cmd`` does not reproduce Astromancer's off-by-one isochrone
      splice index (its extraction defect #3).

See ``docs/extraction.md``, "HR Diagram (Python)" for the full record.

Core transform (matches computePlotDelta exactly)
-------------------------------------------------
    dx = A(red) - A(blue)                         # colour excess
    dy = -A(lum) - 5*log10(d_pc) + 5              # distance modulus term
    HR frame: shift STARS by +(dx,dy)  ->  absolute-magnitude diagram
    CM frame: shift ISOCHRONE by -(dx,dy)  (same fit, opposite frame)

    A(lambda) comes from the Cardelli-Clayton-Mathis (1989) law, evaluated at
    each filter's effective wavelength - not from per-band constants.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial import cKDTree


# ---------------------------------------------------------------------------
# Filter effective wavelengths (microns).
#
# NOTE ON PARITY: these are standard literature values. Astromancer carries its
# own `filterWavelength` table in cluster.util.ts (20 filters). B and V agree to
# ~0.1%, but Cousins R/I and the survey bands are sensitive to the exact value,
# so for bit-for-bit parity copy Astromancer's table over this dict.
# ---------------------------------------------------------------------------
FILTER_WAVELENGTH: dict[str, float] = {
    "U": 0.365, "B": 0.44, "V": 0.55, "R": 0.64, "I": 0.80,   # Johnson-Cousins
    "J": 1.25, "H": 1.65, "K": 2.19,                          # 2MASS
    "G": 0.673, "BP": 0.532, "RP": 0.797,                     # Gaia
    "u": 0.354, "g": 0.475, "r": 0.622, "i": 0.763, "z": 0.905,  # SDSS/APASS
    "W1": 3.35, "W2": 4.60,                                   # WISE (see warning)
}


# ---------------------------------------------------------------------------
# Cardelli-Clayton-Mathis (1989) extinction law, A(lambda)/A(V) = a(x) + b(x)/Rv
# ---------------------------------------------------------------------------
def _ccm_a_b(x: float) -> tuple[float, float]:
    """CCM a(x), b(x) for x = 1/lambda in inverse microns."""
    if 0.3 <= x <= 1.1:                                   # infrared
        a = 0.574 * x ** 1.61
        b = -0.527 * x ** 1.61
    elif 1.1 < x <= 3.3:                                  # optical / NIR
        y = x - 1.82
        a = (1 + 0.17699 * y - 0.50447 * y**2 - 0.02427 * y**3 + 0.72085 * y**4
             + 0.01979 * y**5 - 0.77530 * y**6 + 0.32999 * y**7)
        b = (1.41338 * y + 2.28305 * y**2 + 1.07233 * y**3 - 5.38434 * y**4
             - 0.62251 * y**5 + 5.30260 * y**6 - 2.09002 * y**7)
    elif 3.3 < x <= 8.0:                                  # ultraviolet
        Fa = Fb = 0.0
        if x >= 5.9:
            Fa = -0.04473 * (x - 5.9)**2 - 0.009779 * (x - 5.9)**3
            Fb = 0.2130 * (x - 5.9)**2 + 0.1207 * (x - 5.9)**3
        a = 1.752 - 0.316 * x - 0.104 / ((x - 4.67)**2 + 0.341) + Fa
        b = -3.090 + 1.825 * x + 1.206 / ((x - 4.62)**2 + 0.263) + Fb
    else:
        raise ValueError(f"wavelength out of CCM range (1/lambda = {x:.3f} um^-1); "
                         "WISE/mid-IR bands are not covered.")
    return a, b


def get_extinction(band_or_wavelength, ebv: float, rv: float = 3.1) -> float:
    """
    A(lambda) in magnitudes for a given E(B-V), via CCM.

    Accepts either a band name (looked up in FILTER_WAVELENGTH) or a wavelength
    in microns. Mirrors cluster.util.ts::getExtinction, which returns
    Rv*E(B-V)*(a + b/Rv) == A_V*(a + b/Rv).

    (Astromancer hard-codes the leading factor as 3.1 regardless of `rv`; that
    is defect #1 in the extraction record. This version uses `rv` throughout,
    which is identical for the default rv=3.1 and correct otherwise.)
    """
    lam = FILTER_WAVELENGTH[band_or_wavelength] if isinstance(band_or_wavelength, str) \
        else float(band_or_wavelength)
    a, b = _ccm_a_b(1.0 / lam)
    return rv * ebv * (a + b / rv)


def distance_modulus(distance_kpc: float) -> float:
    """mu0 = m - M for a distance in kiloparsecs = 5*log10(d_pc) - 5."""
    return 5.0 * np.log10(distance_kpc * 1000.0) - 5.0


def compute_plot_delta(blue, red, lum, distance_kpc, ebv, rv=3.1):
    """
    (dx, dy) offset between the observed CM plane and the absolute HR plane,
    matching Astromancer's computePlotDelta.
    """
    A_blue = get_extinction(blue, ebv, rv)
    A_red = get_extinction(red, ebv, rv)
    A_lum = get_extinction(lum, ebv, rv)
    dx = A_red - A_blue
    dy = -A_lum - 5.0 * np.log10(distance_kpc * 1000.0) + 5.0
    return dx, dy


# ---------------------------------------------------------------------------
# 1. Load photometry and apply the max-error quality cut
# ---------------------------------------------------------------------------
def load_photometry(path, blue, red, lum, err_suffix="_err", max_error=None):
    """Read a photometry CSV; optionally drop stars whose error in any used
    band exceeds `max_error`. Expects columns like B, B_err, V, V_err, ..."""
    df = pd.read_csv(path)
    used = {blue, red, lum}
    missing = [c for c in used if c not in df.columns]
    if missing:
        raise KeyError(f"CSV missing magnitude columns {missing}. Have: {list(df.columns)}")
    df = df.dropna(subset=list(used))
    if max_error is not None:
        mask = np.ones(len(df), dtype=bool)
        for band in used:
            ecol = band + err_suffix
            if ecol in df.columns:
                mask &= df[ecol].values <= max_error
        df = df[mask]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. Observed photometry -> absolute-magnitude CMD (HR frame: shift stars +delta)
# ---------------------------------------------------------------------------
def to_absolute_cmd(df, blue, red, lum, distance_kpc, ebv, rv=3.1):
    """Return (colour0, M_lum): de-reddened colour and absolute magnitude."""
    dx, dy = compute_plot_delta(blue, red, lum, distance_kpc, ebv, rv)
    colour0 = (df[blue].values - df[red].values) + dx
    m_lum = df[lum].values + dy
    return colour0, m_lum


def _errors(df, blue, red, lum, err_suffix):
    def col(name):
        c = name + err_suffix
        return df[c].values if c in df.columns else np.zeros(len(df))
    s_colour = np.sqrt(col(blue) ** 2 + col(red) ** 2)
    s_mag = col(lum)
    s_colour = np.where(s_colour > 0, s_colour, 1.0)
    s_mag = np.where(s_mag > 0, s_mag, 1.0)
    return s_colour, s_mag


#: Magnitudes fainter than this in an isochrone are sentinel rows, not stars.
SENTINEL_ABS_MAG = 25.0


# ---------------------------------------------------------------------------
# 3. Isochrone loading (PARSEC / CMD style) - native order is PRESERVED
# ---------------------------------------------------------------------------
def load_isochrone(path):
    """Parse a PARSEC (stev.oapd.inaf.it/cmd) isochrone table. The last commented
    (#) line before the data holds the column names."""
    header = None
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("#"):
                header = s.lstrip("#").split()
            elif s:
                break
    return pd.read_csv(path, sep=r"\s+", comment="#", header=None, names=header)


def select_isochrone(iso, logage, mh=None, age_col="logAge", mh_col="MH"):
    """Pick the single isochrone nearest a target logAge (and optionally [M/H])."""
    sub = iso
    if mh is not None and mh_col in sub.columns:
        uniq = np.unique(sub[mh_col].values)
        sub = sub[sub[mh_col] == uniq[np.argmin(np.abs(uniq - mh))]]
    ages = np.unique(sub[age_col].values)
    return sub[sub[age_col] == ages[np.argmin(np.abs(ages - logage))]].reset_index(drop=True)


def isochrone_cmd(iso, blue_col, red_col, lum_col, iskip=None, label_col="label", max_label=7,
                  max_abs_mag=SENTINEL_ABS_MAG):
    """
    Colour and absolute magnitude arrays for a selected isochrone, kept in the
    file's NATIVE order (ascending initial mass) so the plotted polyline traces
    MS -> turnoff -> giant correctly.

    (My earlier version sorted by magnitude, which zig-zags a real track at the
    turnoff. Astromancer keeps native order and breaks the line at `iSkip`; pass
    that index here to insert a NaN gap for plotting.)

    A raw PARSEC/COLIBRI table (unlike whatever pre-cleaned track Astromancer's
    backend hands over) carries the evolutionary-phase `label` column, and once
    a track enters thermally-pulsing AGB (label 8+: PARSEC's own dust/mass-loss
    modelling breaks down there) `Mini` stops advancing while Gaia BP/RP swing
    by tens of magnitudes pulse to pulse. Plotted or fit against verbatim, that
    turns into a scribbled "wedge" dominating the CMD and, worse, gives
    `_weighted_cost` a field of spurious near-main-sequence attractor points
    that bias the distance/E(B-V) solve. Rows with `label > max_label` are
    dropped before anything else runs; pass `max_label=None` to disable.

    The local Girardi grid has no `label` column. Most of its tracks end in a
    sentinel row with every band near 30 mag, which no star is: plotted, it
    drew a line from the track's end to M ~ 30. Rows with any of the three
    bands fainter than `max_abs_mag` are dropped; pass `None` to keep them.
    """
    if max_label is not None and label_col in iso.columns:
        iso = iso[iso[label_col] <= max_label].reset_index(drop=True)
    if max_abs_mag is not None:
        bands = iso[[blue_col, red_col, lum_col]].to_numpy(dtype=float)
        iso = iso[~(np.abs(bands) > max_abs_mag).any(axis=1)].reset_index(drop=True)
    colour = iso[blue_col].values - iso[red_col].values
    mag = iso[lum_col].values.astype(float)
    if iskip is not None and 0 < iskip < len(mag):
        # off-by-one in Astromancer's splice (extraction defect #3) is NOT copied
        colour = np.insert(colour, iskip, np.nan)
        mag = np.insert(mag, iskip, np.nan)
    return colour, mag


# ---------------------------------------------------------------------------
# 4. Fitting (an ADDITION - Astromancer is a manual by-eye tool, no optimizer)
# ---------------------------------------------------------------------------
#: Added in quadrature to each star's colour and magnitude errors. Gaia DR3
#: quotes ~3 mmag for a bright star, far below how well any model isochrone
#: matches a real cluster; without a floor the brightest few stars set the
#: whole fit.
SYSTEMATIC_FLOOR_MAG = 0.02
#: The most one star may add to the cost. Blue stragglers, binaries and field
#: stars sit far from any single-star isochrone; uncapped, a dozen of them
#: (32,000 each in M67) outweighed the whole main sequence and pulled the fit
#: to a younger, bluer turnoff with extra reddening to compensate.
CHI2_CAP = 9.0
#: A track's points are 0.08-0.27 mag apart on the main sequence. The cost is
#: the distance to the track, so it is resampled at this step first; a star on
#: the track between two points no longer reads as a miss.
TRACK_STEP_MAG = 0.005
#: Consecutive points further apart than this are a jump between evolutionary
#: phases (the grid has no phase labels), and are not joined.
TRACK_MAX_GAP_MAG = 0.5
#: How many nearest resampled points are compared exactly for each star.
_NEIGHBOURS = 16


def _resample_track(colour, mag, step=TRACK_STEP_MAG, max_gap=TRACK_MAX_GAP_MAG):
    ok = np.isfinite(colour) & np.isfinite(mag)
    colour, mag = colour[ok], mag[ok]
    xs, ys = [colour[:1]], [mag[:1]]
    for k in range(len(colour) - 1):
        length = np.hypot(colour[k + 1] - colour[k], mag[k + 1] - mag[k])
        if length == 0 or length > max_gap:
            xs.append(colour[k + 1:k + 2]); ys.append(mag[k + 1:k + 2])
            continue
        t = np.arange(1, int(np.ceil(length / step)) + 1) / np.ceil(length / step)
        xs.append(colour[k] + t * (colour[k + 1] - colour[k]))
        ys.append(mag[k] + t * (mag[k + 1] - mag[k]))
    return np.concatenate(xs), np.concatenate(ys)


class _TrackCost:
    """Capped chi-square of each star's distance to a resampled isochrone.

    The nearest point is found with a KD-tree in a frame scaled by the median
    errors, then the ``_NEIGHBOURS`` candidates are compared with each star's
    own errors. With the floor the errors are close to uniform, so the scaled
    nearest points contain the true one."""

    def __init__(self, s_colour, s_mag, iso_colour, iso_mag,
                 floor=SYSTEMATIC_FLOOR_MAG, cap=CHI2_CAP):
        self.ic, self.im = _resample_track(np.asarray(iso_colour, float), np.asarray(iso_mag, float))
        self.sc = np.sqrt(s_colour**2 + floor**2)
        self.sm = np.sqrt(s_mag**2 + floor**2)
        self.scale = (float(np.median(self.sc)), float(np.median(self.sm)))
        self.tree = cKDTree(np.c_[self.ic / self.scale[0], self.im / self.scale[1]])
        self.k = min(_NEIGHBOURS, len(self.ic))
        self.cap = cap

    def __call__(self, colour, mag):
        _, idx = self.tree.query(np.c_[colour / self.scale[0], mag / self.scale[1]], k=self.k)
        idx = np.asarray(idx).reshape(len(colour), -1)
        dc = (colour[:, None] - self.ic[idx]) / self.sc[:, None]
        dm = (mag[:, None] - self.im[idx]) / self.sm[:, None]
        chi2 = (dc**2 + dm**2).min(axis=1)
        if self.cap is not None:
            chi2 = np.minimum(chi2, self.cap)
        return float(chi2.sum())


def fit_distance_reddening(df, blue, red, lum, iso_colour, iso_mag,
                           x0=(1.0, 0.1), err_suffix="_err",
                           d_bounds=(0.05, 100.0), ebv_bounds=(0.0, 3.0), rv=3.1,
                           floor=SYSTEMATIC_FLOOR_MAG, cap=CHI2_CAP):
    """Optimize distance (kpc) and E(B-V) so data best overlays a fixed isochrone.

    ``x0`` centres a coarse grid (distance x0.6-x1.5, E(B-V) from 0 to the
    larger of 0.8 and twice x0's), and Nelder-Mead polishes its best point.
    Started at ``x0`` alone, it settled in a second minimum at many ages, which
    made the ranking of ages close to random."""
    s_colour, s_mag = _errors(df, blue, red, lum, err_suffix)
    track = _TrackCost(s_colour, s_mag, iso_colour, iso_mag, floor=floor, cap=cap)

    def cost(p):
        d, ebv = p
        if not (d_bounds[0] <= d <= d_bounds[1]) or not (ebv_bounds[0] <= ebv <= ebv_bounds[1]):
            return 1e12
        c, m = to_absolute_cmd(df, blue, red, lum, d, ebv, rv)
        return track(c, m)

    distances = x0[0] * np.exp(np.linspace(np.log(0.6), np.log(1.5), 37))
    reddenings = np.linspace(0.0, max(0.8, 2.0 * x0[1]), 41)
    grid = np.array([[cost((d, e)) for e in reddenings] for d in distances])
    i, j = np.unravel_index(grid.argmin(), grid.shape)
    res = minimize(cost, (distances[i], reddenings[j]), method="Nelder-Mead",
                   options={"xatol": 1e-4, "fatol": 1e-4, "maxiter": 2000})
    d, ebv = res.x
    return {"distance_kpc": float(d), "ebv": float(ebv), "cost": float(res.fun),
            "reduced_cost": float(res.fun / max(len(df), 1)), "success": bool(res.success)}


def fit_cluster(csv_path, iso_path, blue, red, lum,
                iso_blue, iso_red, iso_lum, logages, mh=None,
                max_error=None, err_suffix="_err", x0=(1.0, 0.1), rv=3.1):
    """Scan logAges, fit distance & E(B-V) for each, return best + ranked trials."""
    df = load_photometry(csv_path, blue, red, lum, err_suffix, max_error)
    iso_all = load_isochrone(iso_path)
    trials = []
    for la in logages:
        iso = select_isochrone(iso_all, la, mh)
        ic, im = isochrone_cmd(iso, iso_blue, iso_red, iso_lum)
        fit = fit_distance_reddening(df, blue, red, lum, ic, im,
                                     x0=x0, err_suffix=err_suffix, rv=rv)
        fit["logage"] = la
        trials.append(fit)
    trials.sort(key=lambda t: t["cost"])
    return {"best": trials[0], "trials": trials, "n_stars": len(df)}


# ---------------------------------------------------------------------------
# 5. Plotting
# ---------------------------------------------------------------------------
def plot_cmd(colour, mag, iso_colour=None, iso_mag=None,
             xlabel="(B - R)$_0$", ylabel="M$_V$", title=None,
             ax=None, frame_on_data=False):
    import matplotlib.pyplot as plt
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 7))
    ax.scatter(colour, mag, s=10, c="#33b3e6", alpha=0.8, label="Photometry", zorder=2)
    if iso_colour is not None:
        ax.plot(iso_colour, iso_mag, color="#5b3fd6", lw=2, label="Isochrone", zorder=3)
    if not ax.yaxis_inverted():
        ax.invert_yaxis()
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.grid(alpha=0.15); ax.legend(loc="lower left", frameon=False)
    if frame_on_data:
        px = 0.1 * (np.nanmax(colour) - np.nanmin(colour) + 1e-6)
        py = 0.1 * (np.nanmax(mag) - np.nanmin(mag) + 1e-6)
        ax.set_xlim(np.nanmin(colour) - px, np.nanmax(colour) + px)
        ax.set_ylim(np.nanmax(mag) + py, np.nanmin(mag) - py)
    return ax
