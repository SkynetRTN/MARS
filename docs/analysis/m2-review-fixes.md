# M2 comprehensive review corrections

2026-10-26, on `feature/m2` after the read-only audit of `62da5cc`.
The audit covered all ten M2 checkpoints. Its existing suite passed 4,036
tests with 88 skips, but independent probes found five P2 issues and one P3.
This record describes their corrections rather than treating that green run as
evidence that the reported inputs were already correct.

## Scientific outputs and acceptance

**Pulsar centering.** Twenty observations near `0.1`, with one changed by one
ULP, previously gave power `9.397362383022582` and a Gaussian false-alarm bound
`4.2704930090651965e-11`. Removing the baseline gave power
`0.006722674417646273` and bound `0.994300111480826`; independent QR agreed with
the latter. Both the power and residual paths now center observed-value offsets
at a safe scale, then use the same normalized response. This also avoids
underflow/overflow of the response variance on tiny/large finite baselines.
The unit-impulse reference, translation invariance and saved ECSV values are
checked in both coordinate modes at `0.1`, `-0.1`, `1e-300` and `1e300`.
Exact constants remain rejected, with no tolerance hiding real variation.

Previously saved M2 residual statistics can contain the centering error. New
spectra include `false_alarm_flux_centering=observed_offsets`; plotting requires
that marker as well as the residual-statistic/method markers to label thresholds
as current. Earlier levels warn and plot as uncalibrated; recompute from the
light curve. The grid and Gaussian-noise assumptions are unchanged. This
correction is numerical stabilization, not a certified probability enclosure.

**Singular WCS.** A nonzero rank-one CD matrix could have finite forward
coordinates and a nonempty footprint while its inverse returned NaN. The
validator now requires a finite log determinant and nonzero sign for the
effective celestial matrix before acceptance or header writes. `slogdet`
avoids underflow from directly multiplying tiny valid scale elements. Tests
reject CD and PC representations through both backend result paths and preserve
the input header; a small valid anisotropic candidate remains accepted.
Native extraction/solver boundaries are substituted; real solver convergence
and arbitrary distortion invertibility are not established by these checks.

## Benchmark attribution

**Qualification scope.** Bare scientific content such as “used interpolation”
or “analyzed training data” previously exempted an invented author. The grader
now recognizes explicit citation qualifications: a leading background/memory
qualification, a directly parenthesized qualification, or an explicit unverified
citation. Unrelated trailing/negated qualifications do not excuse the author.
Ordinary method words remain assertions. Existing direct-denial controls remain.

**Identifier association.** Honorifics/initials and a soft line wrap previously
hid a sentence's explicit bibcode, allowing an author from another returned
paper to support the wrong identifier. Context now preserves common scholarly
abbreviations and wrapped prose while respecting paragraph/list boundaries and
complete Markdown table rows. Positive tests keep neighboring supported authors
and independently identified rows from borrowing each other's bibcodes.

The grammar remains deterministic and bounded; it is not a general language
parser or a check that a paper supports a scientific conclusion. Catalog names,
nicknames, arbitrary prose and unrecognized citation forms retain their stated
limits. Task keys are unchanged because their intended hard-check requirements
are unchanged. Historical scores remain attribution-unchecked and unregraded;
no new paid sessions or retrospective ranking is claimed. Any original sessions
graded by an earlier implementation require regrading together before comparison.

## Failure boundaries

**Memory limits.** Public photometry now lets allocation failures reach MCP's
existing `resource_limit` handler, including failures while producing fallback
file metadata. Ordinary computation/plot failures still return their collected
warnings. Tests use the real dispatcher and check both compute and plot phases.

**HR artifact writes.** Ordinary artifact construction/write failures now return
an error containing notices from the completed extraction. Real-frame tests
substitute only the failed artifact writer, covering OSError and ValueError.
MemoryError retains its resource classification. No failed write is described
as a successful extraction artifact.

## Validation

Every original failure class was observed in a failing regression before its
fix. The corrected tests include public results/artifacts, native boundary
substitutes, positive controls and independent numeric references. Focused
validation passed **460 tests** before final review.

Fresh review exposed three additional attribution edge cases in the initial
correction: absolute-value prose containing pipes, combined/cell-local genuine
qualifications and negated scientific confirmation. Eleven regressions failed
before the correction; an additional first-column GFM qualification regression
protected the row's left boundary. The attribution suite then passed all 67
checks. Independent
review's 210 QR comparisons found maximum discrepancies of `2.67e-15` in power
and `1.12e-15` in residual fraction. No additional actionable scientific or
failure-boundary issue was established in that review.

The full suite also exposed an obsolete expectation that resolvable tiny flux
must be rejected because its unscaled variance underflowed. That case now
checks the independently derived Nyquist power `4/3` at unit, tiny and large
amplitude. True degenerate/nonfinite inputs retain their rejection tests.

Final complete suite: **4,094 passed, 88 skipped, 220 warnings in 918.18 seconds**,
Python 3.13.15 with locked dependencies and MCP. There are 58 net added cases.
Compilation, schema goldens, generated guidance, repository shape and whitespace
checks pass. Live-service, paid-transcript, native Windows and external solver
data retain their independent gates/skips. No new paid run or historical regrade
was performed. The [implementation plan](../working/m2-review-fixes.md) records
the intermediate red/green evidence and rulings.

Catalog magnitudes, H-alpha transforms, calibration fitting/error propagation,
public inputs and branch topology are unchanged. Other M3/release/live-service
and native-data gates remain independent of these six fixes.
