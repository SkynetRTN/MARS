# Legacy coordinates, extinction and mass

M2 correction on `feature/m2`, recorded 2026-10-22. This checkpoint concerns
the exported helpers in `algorithms/hrdiagram_py/legacy.py`. A source search
found no registered-tool callers of their coordinate formatting, plot
transforms, dispersion or cluster-summary APIs. The registered HR fitter uses
`hrfit.py` and the independent membership pipeline; their formulas and outputs
are unchanged. This record does not claim a new fit to a real cluster.

## Signed sexagesimal coordinates

`d2_dms` and `d2_hms` retain three-component lists. The first component now
carries the sign of the entire angle, and minutes/seconds are nonnegative.
For example, `-30.5` degrees becomes `[-30.0, 30, 0.0]` in DMS and
`[-2.0, 2, 0.0]` in HMS. Subdegree/subhour negative angles retain a negative
floating zero in the first component: `-0.5` degrees is `[-0.0, 30, 0.0]`
in DMS. Negative zero itself retains its sign.

Consumers must preserve and inspect that sign, including with `copysign` or
`signbit`; casting the first component to an integer loses subunit signs.
Reconstruction applies its sign to the whole absolute triple. HMS is a signed
angle conversion, without automatic 24-hour wrapping. The representation is
checked against [Astropy Angle](https://docs.astropy.org/en/stable/api/astropy.coordinates.Angle.html)
and explicit round trips, rather than the old sign-discarding parity literal.

## Supported extinction model

The helper implements the infrared and optical branches of CCM89:
`0.3 <= 1/lambda < 3.3`, with wavelength in microns. Both the `0.3` endpoint and
the optical branch starting at `1.1` are supported. WISE W1–W4 lie outside this
implemented range and raise `ValueError`, including through legacy HR/CM
transforms, rather than claiming zero extinction. Unknown filters also fail
explicitly. No mid-infrared law or extrapolation is introduced.

`R(V)` must be finite in `[2, 6]`, and `E(B-V)` finite and nonnegative. The
coefficient is now `R(V)*E(B-V)*(a + b/R(V))`; plot transforms propagate an
optional `rv` parameter, defaulting to `3.1`. These domains and coefficients
are checked against the [official CCM89 model](https://dust-extinction.readthedocs.io/en/stable/api/dust_extinction.parameter_averages.CCM89.html)
and its [published reference implementation](https://dust-extinction.readthedocs.io/en/stable/_modules/dust_extinction/parameter_averages.html).
The full CCM89 model has additional ultraviolet branches; this legacy helper
continues to support only its implemented infrared/optical branches.

The V wavelength changes from `0.54` to the standard nominal `0.55` microns.
At `E(B-V)=0.2`, `R(V)=3.1`, the monochromatic V result is
`0.6192870019303767` mag. CCM's exact optical normalization is at
`1/lambda=1.82`, close to this nominal wavelength. Fixed effective wavelengths
approximate broad passbands: neither `A(V)=R(V)*E(B-V)` nor a B-minus-V color
excess is claimed exact for these monochromatic evaluations. Spectral shape,
filter transmission and band-integrated reddening are not modeled.

## Observed proper-motion RMS

The old statistic averaged a subset of radial proper-motion offsets selected
by asymmetric percentiles. Correcting only its slice limits would still not
produce a one-dimensional dispersion. The replacement reports

```text
sigma_pm = sqrt(sum((pm_ra - center_ra)^2 + (pm_dec - center_dec)^2) / (2*N))
```

This is the observed one-dimensional RMS about the supplied center under
isotropy. For two components with common second moment `sigma^2`, the mean
squared radial offset is `2*sigma^2`. Every paired observation contributes;
there is no percentile trimming, Bessel correction, uncertainty weighting or
measurement-noise subtraction. Missing pairs are omitted and nonfinite paired
measurements or empty samples fail explicitly. For finite representable
offsets, component scaling avoids unnecessary intermediate squared-energy
underflow/overflow. Offsets that overflow on subtraction are rejected.

Inputs and output use mas/yr, with orthogonal tangent-plane components:
`pm_ra` must be `mu_alpha* = cos(dec)*dRA/dt`, and `pm_dec = dDec/dt`, with a
center in the same convention. The summary retains its legacy center from the
upper middle element of supplied, sorted PM arrays. This center need not be a
known population mean; the result is not an unbiased sample standard deviation
or a measurement of intrinsic cluster dispersion. Anisotropy, bulk-motion
perspective gradients, binaries and astrometric covariances are unmodeled.

## Radius and mass scope

The historical `get_half_light_radius` actually returns an upper-median
projected **number** radius, in degrees. It has no luminosity weights. The
legacy angular-to-physical conversion is retained and returns light-years for
distance in kpc. It remains a projected-radius proxy, rather than a new
three-dimensional structural estimate.

`get_mass` retains its arithmetic and rounded constants. Together its two
apparently inconsistent unit factors yield the correct conversion
`v[km/s] ~= 4.74 * mu[mas/yr] * distance[kpc]`; correcting either factor alone
would introduce a factor of a million in mass. Independent Astropy units and
constants reproduce the result to `1e-4` relative tolerance over three scales.

The scalar is the retained `eta=10` virial proxy, `eta*sigma_v^2*radius/G`, in
solar masses. An observed RMS, a number-weighted projected radius, isotropy,
assumed equilibrium and a fixed structural coefficient do not establish a
calibrated dynamical mass. The importance of structural assumptions is also
discussed by [Fleck et al.](https://arxiv.org/abs/astro-ph/0604194).

Cluster summaries keep their existing numeric field names and add `units`,
`methods` and structured `warnings`. In particular, `velocityDispersion` is
angular observed scatter in mas/yr, not km/s; `physicalRadius` is in light-years,
`distance` in kpc and `mass` in solar masses. Warnings identify observed-motion
scatter and the virial-mass proxy. Direct scalar helpers document these same
meanings. Consumers that iterate only numeric summary values must select the
numeric fields when reading this additive metadata.

## Validation

`tests/test_hrdiagram_legacy_science.py` contains 51 cases. The first run of 49
cases had 38 failures against the old implementation, with positive-coordinate
controls and the protected mass-unit checks passing. An additional RMS case
reproduced intermediate radial-norm overflow even though the one-dimensional
result was finite; component scaling corrects that case. Constant-motion
scatter is also pinned at zero. Affected preservation assertions intentionally
change for signed coordinates, the RMS definition and additive summary data.

Focused legacy science, cluster/HR and M1 scientific safeguards: **144 passed**.
Independent code review passed 64 science/preservation tests, adjacent
sexagesimal-boundary probes and all supported filters at R(V) 2, 3.1, 5 and 6.
Its 500 finite-scale RMS comparisons against 100-digit Decimal references
(`1e-300` through `1e300`) differed by at most `2.22e-16` relative. There are no
outstanding code findings. Documentation review's numerical-scope wording
correction is applied.

Python 3.13.15 with locked dependencies and `[mcp]`: full offline suite
**3,565 passed, 49 skipped**, with the same 198 existing warnings. Compileall,
schema goldens, generated-skill consistency, repository shape and
`git diff --check` pass. Skips retain live-service, untracked benchmark,
native Windows and external solver-data gates. This is the fifth closed M2
checkpoint; the remaining release gates are open. The work remains local,
unmerged and unpublished.
