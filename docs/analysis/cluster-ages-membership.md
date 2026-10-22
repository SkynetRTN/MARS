# Cluster ages and membership

M2 correction recorded 2026-10-22 on the single working branch `feature/m2`.
This checkpoint corrects three exported helpers in
`algorithms/hrdiagram_py/legacy.py`. A caller search found no registered tool
using these helpers: `tools.hr_diagram.select_cluster_members` calls the
separate `membership.py` implementation, which already accepts measured zero
motion. These corrections support the legacy Python API; they do not change
the newer HR fitter or introduce membership probabilities.

## Age units and display window

MWSC supplies logarithmic ages in years. The
[CDS MWSC catalogue description](https://cdsarc.cds.unistra.fr/viz-bin/ReadMe/J/A%2BA/558/A53?format=html&tex=true)
identifies `logt` as the base-ten logarithm of cluster age in years. The helper's
output is Myr, so `log_age=9` must yield `1000`, rather than being discarded by
a cutoff of `13.8` applied to Myr.

The existing upper display window is retained as 13.8 Gyr, or 13,800 Myr,
with a strict upper boundary. It is a display policy inherited from the
original code, not an age measurement or cosmological validation. The helper
checks finite logarithmic ages against that ceiling before exponentiation,
then calculates `10**(log_age - 6)`. Missing/nonfinite ages, values beyond the
window and ages that underflow to zero are omitted. Results remain sorted.

## Source-ID joins

The old merge sorted result IDs numerically but compared them with source IDs
as strings. Sources `['1', '10', '2']` could silently lose the result for `10`.
The replacement indexes results by their exact ID without sorting or numeric
conversion. Leading zeros, large integer identifiers and nonnumeric string
identifiers remain distinct under their original Python equality semantics.

The original source list and dictionaries are updated in place, with source
order preserved. Unmatched sources retain their previous `fsr` value, and
the result list is not reordered or modified. When a result ID is repeated,
the first result wins, retaining the existing first-match convention.

## Measured proper motion

Both proper-motion components must be present and finite, including when the
selection has no proper-motion bounds. A finite zero is a measurement and is
accepted when it falls within the requested selection. Missing, NaN and
infinite components are rejected.

Bounded selections use the inclusive ellipse defined by the two axis ranges.
A zero-width axis defines a closed line segment; two zero-width axes define
a point. These cases no longer divide by zero. The distance cut, partition
order and source objects are retained. This is a deterministic geometric
selection, not a statistically calibrated membership probability. Proper-motion
units remain those of the supplied catalogue and bounds; no conversion is
introduced.

## Acceptance evidence

`tests/test_cluster_ages_membership.py` has 23 cases covering old clusters up
to log-age 10.1, invalid/extreme ages without exponentiation overflow,
three source orderings, opaque IDs, duplicate/unmatched results, finite zero
motion with and without bounds, both missing/nonfinite components, ellipse
boundaries and zero-width selections. A join-to-selection regression keeps
the previously lost zero-motion source `10`.

The first run reproduced 14 failures in 17 cases before implementation. The
updated legacy preservation assertion intentionally expects a 1 Gyr cluster
to appear at 1,000 Myr. An offline public-tool check writes and rereads the
actual membership ECSV artifact, preserving zero-motion sources while
rejecting a missing-motion row and an outlier; only its literature lookup is
stubbed. Existing HR fitting and membership tests remain separate checks.

## Validation

Focused cluster/HR and variable-star scientific/limit tests: **105 passed**.
Independent review ran all five cluster/HR test files: **62 passed**. It also
checked the strict age ceiling, mixed identifiers, duplicates and degenerate
ellipses, with no outstanding code or documentation findings.

Full offline branch validation on Python 3.13.15 with locked dependencies and
`[mcp]`: **3,503 passed, 49 skipped**, with 198 existing warnings. This includes
the variable-star response-amplitude review correction. Compileall, schema
goldens, generated-skill consistency, repository shape and `git diff --check`
pass. Skips retain the existing live-service, untracked benchmark, native
Windows and external solver-data gates. This is the fourth closed M2
checkpoint; the branch remains local, unmerged and unpublished.
