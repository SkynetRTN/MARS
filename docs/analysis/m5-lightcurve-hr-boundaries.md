# M5: light-curve and HR boundaries

Investigated 2026-11-04 against `7375f82` on `feature/m5-geometry`, following
the first three completed M5 squares. The [master plan](../working/master-continuation-plan.md#m5-resolve-the-specific-older-reports-that-remain-unverified)
defines the scope; the [investigation plan](../superpowers/plans/2026-11-04-m5-lightcurve-hr-boundaries.md)
records the probes. **Production behavior is unchanged.** Characterization
tests explicitly pin current defects or conventions; passing them does not
accept a repair. This M5 square remains open for its unresolved findings.

## Findings and dispositions

| Report | Current result | Reachability/disposition |
|---|---|---|
| TS-12: period step rounds to zero | `get_period_step(.1, 5)` returns 0 although its unrounded step is 0.00002 days; `.2,10` likewise erases 0.00004. | Confirmed retained helper defect, P3. No maintained production caller uses it; actual public grids validate progress and compute independently. |
| TS-24 + TS-25: maximum-bin endpoint and phase-one mapping | Pulsar folding maps the origin and exact period multiples to P, then binning can exclude every tied maximum sample. Three planted pulses disappear completely through real load/fold/audio stages. | Confirmed maintained-path defect, P2. The old wording “always drops one sample” is too narrow and too absolute: tie multiplicity and float division affect the result. |
| M5-LC-01: duplicated-cycle plot extent lost | A two-cycle artifact omits its `display_period`; the plot reloads a one-cycle default and clips the duplicate cycle. | Confirmed maintained artifact/plot defect, P2. Actual PNG axes hide all three second-cycle bins in the reproduction. |
| TS-26: independently supported channels paired by index | Direct independently binned arrays produce incorrect differences/sums when their occupied phase bins differ. | Confirmed latent helper/caller-contract hazard. Current public folding supplies common phase support and validates finite aligned channels, so the old public misalignment consequence is not reproduced. |
| TS-08: prefolded/index axes | Retired `foldSingleSourceByIndex` is absent from live Python. Current standard ingestion interprets column zero as seconds and all files use the time-based fold. | Historical divide-by-count defect is unreachable. Original standard/prefolded coordinate units remain unverified; synthetic index-like input is not proof of that format's intended units. |
| TS-22: luminosity framing depends on red filter | The legacy bright magnitude bound uses `red.faint` in a luminosity expression. BP/RP/G differs by +0.1125 mag from a luminosity-only margin. | Confirmed legacy display-padding defect, P3, outside current HR tools. It does not change fitted values or coordinates. |
| TS-23: isochrone splice drops one point | The legacy helper replaces ordinary point `iSkip-1` with a gap. Maintained `hrfit.isochrone_cmd` instead retains the point and inserts aligned NaNs. | Legacy defect reproduced; maintained Python correction already exists. Current local-grid fitting/plotting preserves ordinary model rows. |
| TS-30: edge-on scales differ | Legacy rendering uses 32 px/kpc horizontally, 16 vertically, and clips height at ±500 px. | Verified rendering convention outside current HR tools. No equal-physical-aspect requirement was established, so it is not newly classified as a physical-science error. |

### Period grids and variable-star boundaries

`algorithms/variable_star/folding.py:125` keeps a minimum-step check at
`1e-5` but formats accepted larger values to four decimals. Ordinary
0.1-day/5-day and 0.2-day/10-day period/baseline pairs pass the check and
return zero. Direct callers remain exposed. Searches through maintained
production code found no use of this slider helper.

The public variable-star periodogram builds its own validated fixed grid.
A real CSV→paired ECSV→periodogram control on a planted 0.1-day sinusoid
spanning five days succeeds while the slider helper returns zero: its periods
advance, powers stay finite in [0,1], and the peak is within 1e-5 days of the
planted period. The retained accumulating grid can include its extra float-drift
endpoint; this is separate from a step that cannot advance. M1's current grid
checks reject unrepresentable progress before computation.

The historical pulsar Nyquist helper also retains five-decimal rounding, but
its current guard rejects a rounded zero rather than searching with it.
The maintained driver uses `sampling.summarize`: one-microsecond spacing
supplies a positive 2e-6-second suggested minimum and a finite default spectrum.
Irregular-data defaults retain their documented median-spacing heuristic;
this investigation does not reopen M2's sampling/significance correction.

Variable-star folding also retains a closed right endpoint for positive exact
multiples: times `[0,1,2]` with P=1 become `[0,1,1]` before sorting, whereas
canonical modulo would give all zeros. Unlike the pulsar path, the origin stays
zero and no subsequent binning removes these rows. Direct neighboring-float
controls and real one-/two-cycle artifacts preserve every magnitude with its
own M3-aligned uncertainty bounds. The artifact's phase column is explicitly
in days. This periodically equivalent endpoint representation is recorded as
a display convention here, not evidence of variable-star flux loss.

### Pulsar endpoint loss and missing diagnostics

`algorithms/pulsar/folding.py:215–218` forms `P + remainder` before adjusting
its origin, mapping the first sample and exact positive multiples to P. The
representable float immediately below P can also coalesce to P in that
addition; the next float above P maps to `2**-52` in the P=1 control.

At `folding.py:257–265`, bin indices use `floor((x-xMin)/binSize)` and an
`index < bins` mask. With P=1, four bins, times `0,.25,...,2`, and flux 9 at
`0,1,2` and zero elsewhere, independent circular-bin means are `[9,0,0,0]`.
The current public result instead contains phases
`[.34375,.53125,.71875]` with flux `[0,0,0]`. **All three pulses disappear.**
The real artifact writer persists that table, so this is not preview truncation.
`samples_folded=9` counts samples before binning; `bins_filled=3` does not disclose
which samples were excluded. The result has `pulse_snr=None` and no warnings.

The same raw file produces silent PCM through actual sonification, with
`flat_light_curve` and `playback_not_real_time` warnings. The weak-pulse check
is guarded by a non-None SNR and does not add `weak_or_absent_pulse`. An
all-boundary `[0,1,2]` input writes a successful **empty folded ECSV**; audio
then returns `invalid_input` because nothing can be sonified.

Endpoint exclusion is not universal. For times `[0,.5,1]`, flux `[9,0,9]`,
P=1, the default 100 bins drops both pulses and yields `[0]`; 99 bins retains
them and yields `[0,9]` because `.5/(.5/99)` rounds below 99. Changing a bin
count can therefore hide this defect rather than fix its boundary policy.

The public periodogram calls the same fold for its empirical diagnostic at
`tools/pulsar.py:618–624`. A bounded one-trial search at P=1 on the nine-sample
curve has finite positive spectral power (about 3.2), but `peak_fold_snr=None`
and no `peak_does_not_fold` warning. This establishes current caller reachability;
a fixed one-trial control does not establish blind period recovery or probability
calibration.

### Channel support, source formats and plotting/audio axes

For independently supported bins, the legacy index-pairing issue remains:
phase supports `[.5,1.5,2.5,3.5]` and `[.5,2.5]` produce differences `[9,9]`
and sums `[11,13]` by index, while matching actual shared phases gives `[9,10]`
and `[11,14]`. Current `fold_lightcurve` supplies both channels the same
`phase_x`, with finite/equal-length guards. Real synchronized-channel artifacts
remain aligned, and an injected NaN hole is rejected as `invalid_input`.
The direct value-only helper has no phase coordinates with which to repair
arbitrary independently supported inputs; callers must establish alignment.

The retired TS-08 implementation was verified from the pre-retirement source
at `b5d1b0a^`: it computed `frequency/sample_count*period`. No live Python
caller reaches that code. Standard ingestion instead copies column zero into
`time_s` (`ingest.py:319`) without an index/phase-unit declaration. With P=2,
flux `[99,2,4,6]`, seconds-like coordinates `[0,.5,1,1.5]` produce phases
`[.6875,1.0625,1.4375]`, flux `[2,4,6]`; index-like `[0,1,2,3]` produces
phase `[1.125]`, flux `[4]`. Both real PNGs say “Time (s)”. These are controls
of current interpretation, not an authoritative definition of the original
standard/prefolded format. A real format contract/sample is needed before
converting those coordinates or claiming a unit correction.

M5-LC-01 is independently reproducible without that format ambiguity.
`fold_pulsar_lightcurve(..., period_s=2, display_period=2)` writes six phase
bins through 3.4375 s and returns a two-cycle result. The table metadata at
`tools/pulsar.py:809–831` saves period and bins but not display extent. Default
`plot_pulsar` reads the missing setting as one cycle at line 1763: the actual
PNG x limits are `(0,2.1)`, clipping all three duplicated bins without warning.
The line data still contains them; the fault is the reloaded plot extent.

A related existing audio limitation is also bounded by the probes. Empty-bin
removal can leave nonuniform phase support, contradicting the documentation's
blanket “uniform by construction” claim for folded profiles. Two real folded
profiles with phases `[.1875,.3125,.4375,.5625]` and
`[.1875,.3125,.6875,.8125]`, both flux `[0,1,0,1]`, produce identical seeded
WAVs and the same global stretch (about 0.7500907). Sonification discards phase
coordinates and renders values uniformly. The existing playback warning remains
relevant; a global stretch does not recover unequal relative gaps. This is not
a new timing-capability implementation or a claim that audio measures a period.

### HR legacy helpers and maintained controls

The legacy `get_standard_view_range` at `legacy.py:448–459` changes its bright
luminosity-axis margin by `(lum.faint-red.faint)/8` compared with a luminosity-only
expression. BP/RP/G gives −13.08375 instead of −13.19625 (+0.1125 mag);
BP/RP/BP differs by +0.2175, and B/R/V by +0.11625. An exploratory enumeration
of 20 framing bands gives 7,600 valid triples with distinct blue/red filters:
7,220 differ; 380 with `red=lum` agree. The largest absolute difference is
0.92 mag. The old “about 0.2 mag” is representative, not a bound. Tests use
seven representative triples rather than thousands of redundant cases.

The legacy splice at `legacy.py:121–129` loses ordinary point `iSkip-1` for
`0<iSkip<n`: four-point controls with skips 1/2/3 lose points 0/1/2 in both
CM and HR frames. Zero, negative, end and outside indices insert no gap.
Maintained `hrfit.isochrone_cmd` deliberately fixed this during the Python port:
its gap NaNs align across axes while every ordinary point survives, including
the tested first/last interior boundaries.

Current tools reach `isochrones.fit_and_compare`→`hrfit` fitting/plotting, not
these three legacy display helpers. A real tool→local-model→optimizer→PNG control
uses the recorded M67 log-age-9.60 track. Of its 338 raw rows, an independently
evaluated sentinel mask identifies only index 337; all **337 retained native
vertices** match direct raw band-column differences and magnitudes. The local
compatibility loader supplies `iSkip=0`, not an old backend discontinuity index.
No remote model or catalog is used.

This is distinct from plot-gap policy. That retained local track has 43
consecutive jumps above 0.5 CMD mag, the largest about 3.368051 between indices
137/138: `(3.582000,-1.896000)`→`(1.219000,0.504000)` (rounded). The plot draws
the native polyline without server break metadata. The fitting cost refuses
interpolation across large jumps: an independent unit-error control gives
0.5625 where bridging would give zero. Whether additional visible breaks are
desired is a display-policy question; it is not the legacy point-loss defect.

Finally, the galaxy offsets at `legacy.py:222–233` take degrees/kpc and return
pixels. Independent Cartesian `(3,4,12)` kpc gives edge offsets `(−96,192)`
and face offsets `(128,−96)`. Equal physical horizontal/vertical components
draw `(−32,16)`, or 26.565051° rather than 45°. Vertical pole clipping starts
at 31.25 kpc, tested immediately below/at/above both signed boundaries.
The historical source and extraction record identify the 32/16/±500 values
as rendering constants. No equal-aspect physical measurement requirement or
current HR-tool caller was found; do not “correct” them as units by assumption.

## Reproduction, validation and remaining work

The three `tests/test_m5_{lightcurve,pulsar,hr}_boundary_investigation.py`
files contain **68 new offline cases**. They include actual CSV/ECSV, PNG and
PCM output and the local recorded HR grid, with direct array/circular-bin,
Cartesian, modulo and raw-model controls. The HR integration replaces only its
remote literature lookup with fixture parameters; it still runs the local model,
optimizer and plot. No production functions are patched to fabricate the
pulsar or variable-star numerical results, and no downloaded fixtures are added.

Focused/related validation: variable-star group **167 passed** (2.97 s);
HR group **127 passed** (38.20 s); existing pulsar group **187 passed**
(233.60 s), plus its **13 new cases passed** separately (0.94 s). These
four invocations cover 494 distinct cases. Final integration and independent
review are recorded below.

Independent review repeated all 68 new cases (3.16 s) and found no material
reachability, science or test-oracle issue. A float32/float64 difference in
reported local-track coordinates was corrected by rounding the illustrative
numbers; no code or conclusion changed.

The first full locked run had **4,731 passed, 94 skipped, one failure** in
`test_mcp_cancellation_releases_sequential_dispatch_lock` (569.81 s). Its
10-second worker-readiness wait expired before the cancellation assertions;
the worker emitted no diagnostic output and was cancelled during cleanup.
Production source was unchanged. A fresh run of all 68 new tests followed by
that MCP case passed **69 tests in 7.00 s**, with the MCP case taking 3.90 s.
The failure and recheck are retained as integration evidence rather than
changing unrelated runtime code or its timeout. Final full validation follows.

The fresh full locked run passed **4,732 tests, 94 skips and 214 FITS
normalization warnings**, no failures, in 428.55 seconds on Python 3.13.15.
Code, tests and guidance stayed unchanged through the failed run, direct
recheck and successful full rerun; only this evidence record was updated.
Compilation, generated guidance consistency and whitespace checks pass.
The 94 skips retain the existing external/asset/platform gates, including
four optional native solver cases from the previous square. This investigation
adds no production behavior change and does not close the light-curve/HR box.

Priorities are the maintained pulsar sample-loss/missing-diagnostic path and
two-cycle artifact/plot handoff. Convert their bug-pinning assertions into
correctness regressions when repairing them. Keep helper-only and already
corrected reports separate; resolve the original standard-coordinate contract
before changing source units, and record HR display choices explicitly.
