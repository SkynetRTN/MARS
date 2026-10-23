# The Pulsar Tool Pipeline

Date: 2026-08-11
Updated: 2026-10-21 (M2 candidate units, sampling and conditional noise bounds)
Status: active architecture

Four tools, one per stage, in the order they must run. This document is the
map from each stage to the extracted Astromancer code that backs it.

A discovery step sits in front of stage 1: `list_pulsar_scans` and
`resolve_pulsar_scan` (`tools.pulsar`, both registered) turn a source name into a
scan path under `data/pulsar/` — override with `MARS_PULSAR_DATA_DIR` —
returning `ToolError`s for misses and ambiguity rather than raising. It is
optional; every stage below also accepts a bare file path.

It also reports the **curated literature period** for a scan
(`curated_period_s`, with `curated_difficulty` and `period_source` alongside),
read from a `curated_periods.json` **beside the scans themselves** — so
`MARS_PULSAR_DATA_DIR` points at another archive and that archive's own
curation is what applies to it. Pinning the map to a fixed repository path
would name-match these five periods onto someone else's files and stamp them
with a `period_source` describing observations they are not.

**It is a check on a measured period, not an input to the pipeline** — see §4,
*Measure first, check second*. Offline it replaces a network call to ATNF for
that check; it does not replace stage 2. A scan the curation does not cover
reports `null` — not recorded, never a substituted number — and a map that is
missing, unreadable or malformed is a `curated_periods_unavailable` warning
carried on both the listing and each scan, not an import error. Rows are
validated one by one, so a row without a numeric `period_s` is dropped rather
than yielding a `period_source` that cites a curation for a number it lacks.

```text
   raw scan (.cal.txt)
          │
          ▼
┌───────────────────────────────┐
│ 1. load_pulsar_lightcurve     │  drop cal block, rebase time,
│                               │  subtract running-median baseline
└───────────────────────────────┘
          │  light curve (.ecsv)  ◄── the handoff every later stage takes
          ├──────────────────────────────────────────┐
          ▼                                          │
┌───────────────────────────────┐                    │
│ 2. compute_pulsar_periodogram │  Lomb-Scargle      │
│                               │  → THE PERIOD      │
└───────────────────────────────┘                    │
          │  period_s                                │
          ├───────────────────┬──────────────────────┤
          ▼                   ▼                      ▼
┌────────────────────┐  ┌──────────────────────────────────┐
│ 3. fold_pulsar_    │  │ 4. sonify_pulsar(period_s=…)     │
│    lightcurve      │  │    folds internally, then renders│
│    → pulse profile │  │    → audio (.wav)                │
└────────────────────┘  └──────────────────────────────────┘
```

---

## 1. Why the order is a dependency, not a convention

Stage 3 needs a period. Stage 2 is the only thing that produces one from the
data. So the sequence is forced, and it is the same sequence the Astromancer
tool's tabs impose on a student: **light curve → periodogram → period folding**,
with sonification hanging off the folding form.

The failure this ordering prevents is specific and quiet. **Folding at a
wrong period can return a flat profile without an error**, which looks
like a faint source rather than a mistake. Harmonics and periodic interference
can also fold coherently, so a strong fold needs interpretation. An agent that guesses a period, or
reads one off the audio, gets a plausible-looking null result with nothing
marking it as wrong. That is why:

- `fold_pulsar_lightcurve` reports `pulse_snr` and warns below 8 sigma;
- `compute_pulsar_periodogram` folds at its own peak and reports
  `peak_fold_snr`, warning `peak_does_not_fold` below 8 sigma. It also reports
  `false_alarm_probability_upper_bound`, conditional on iid Gaussian noise
  and a fixed grid. Read its assumptions; neither that bound nor the empirical
  fold concentration establishes a pulsar or correct period;
- `sonify_pulsar` warns (`unfolded_rendering`) when called without a period;
- every stage's schema says to compare the measured period against a reference —
  stage 0's `curated_period_s` for a bundled scan, `search_atnf` for anything
  else — and to retune rather than substitute when the two disagree.

Stage 4 can run without stage 2, and stage 3 can take a reference period from
stage 0's `curated_period_s` or from `search_atnf` instead of a measured one.
Both are documented on the tools themselves — the second is a fallback with a
reporting obligation attached, not a shortcut.

---

## 2. Stage → algorithm → upstream

Every stage calls a Python module under `algorithms/pulsar/`, ported from
Astromancer. Full provenance, the retired intermediate TypeScript extraction,
and the preserved-quirk list live in `docs/extraction.md` (Pulsar
Sonification; Light Curve; Periodogram) and repository history.

| Stage | Tool | Python algorithm | Astromancer origin |
| --- | --- | --- | --- |
| 1 | `load_pulsar_lightcurve` | `algorithms/pulsar/ingest.py` | `pulsar-light-curve.component.ts::uploadHandler`; `pulsar.service.ts::median`, `backgroundSubtraction` |
| 2 | `compute_pulsar_periodogram` | `algorithms/pulsar/periodogram.py` | `shared/data/utils.ts::lombScargle`; `pulsar-periodogram-highcharts.component.ts::findLocalMax`, `addConfidenceLines` |
| 3 | `fold_pulsar_lightcurve` | `algorithms/pulsar/folding.py` | `pulsar.service.ts::getPeriodFoldingChartData`, `binData`; `pulsar-period-folding-highchart.component.ts::foldAndBin` |
| 4 | `sonify_pulsar` | `algorithms/pulsar/sonification.py` | `pulsar.service.ts::sonification`; `pulsar-period-folding-form.component.ts`, `pulsar-light-curve-sonifier.component.ts` |

`algorithms/pulsar/` is a **port** rather than an extraction under
`algorithms/`, marked `# PORTED:`. Parity is pinned by Python tests; the
intermediate TypeScript extraction remains available in repository history.

---

## 3. The two sonification renderings

Stage 4 has two modes because Astromancer has two call sites, and they are not
equivalent.

| | Folded (`period_s` given) | Light curve (no period) |
| --- | --- | --- |
| Upstream call site | `pulsar-period-folding-form.component.ts` (4 sites) | `pulsar-light-curve-sonifier.component.ts` (2 sites) |
| Status upstream | **primary** | secondary |
| Input | folded, phase-binned profile | raw background-subtracted scan |
| One pass is | one rotation, looped | the whole scan, once |
| Faint source | pulse builds up across rotations | stays buried in noise |
| Audio vs sky time | quantized only (~0.4%) | quantized **and** gap-compressed (~3%) |

Both report `playback_stretch`: audio seconds per second of sky. Neither is
exactly 1.0, because `samplesPerPoint` is floored to a whole number of output
samples rather than fitted to elapsed time. The folded path avoids only the
gap-compression term. **No period should ever be read off the audio.**

---

## 4. Chaining

Each stage takes `path`, which may be a raw scan or the stage-1 `.ecsv`
artifact. Passing the artifact is preferred: it skips the re-ingest and
guarantees every stage sees the same samples.

```python
from tools.pulsar import (
    load_pulsar_lightcurve, compute_pulsar_periodogram,
    fold_pulsar_lightcurve, sonify_pulsar,
)

lc   = load_pulsar_lightcurve("data/pulsar/Skynet_60898_psr_b0329_54_138326_88255.A.cal.txt")
pg   = compute_pulsar_periodogram(lc.artifact.path)
fold = fold_pulsar_lightcurve(lc.artifact.path, pg.peak_period_s)
wav  = sonify_pulsar(lc.artifact.path, period_s=pg.peak_period_s)
```

With the M2 defaults, B0329+54 peaks at **0.714622 s** against the recorded
ATNF reference 0.714519699725801 s (0.0143%), power 400.74, and fold
concentration **231.15**. Its Gaussian-noise FAP bound is 2.69e-177, conditional
on assumptions that the baseline-subtracted radio data does not establish.

Each `pg.top_peaks` entry now has `period_s`, `frequency_hz` and `power`;
there is no mode-dependent `x`. The periods are approximately
`0.7146, 0.3571, 0.2380, 0.1021, 0.1784` — the fundamental and P/2, P/3, P/7,
P/4 harmonics. In either mode, pass a candidate's `period_s` to the fold.
`peak_frequency_hz` is also explicit, and `search_unit` identifies
`search_start`/`search_stop`. The ECSV coordinate column carries seconds or Hz.

Defaults span twice median positive spacing through 3 s, or the reciprocal
band in frequency mode. Irregular data reports `nyquist_period_s=null`,
`sampling_policy=median_spacing_heuristic`, and `suggested_min_period_s` with
a warning: that suggestion is not a universal Nyquist cutoff. Explicit bounds
can use instrument cadence/integration information. Only uniform epochs within
relative tolerance 1e-7 establish the reported Nyquist period; searches above
that frequency warn about aliases. Sampling is rederived on every load rather
than trusted from saved metadata.

The bound uses a finite-sample Beta tail and Bonferroni union inequality over
`evaluated_trials`; frequencies need not be independent. It describes one
fixed finite grid under iid Gaussian errors, not baseline filtering, correlated
noise, RFI, repeated retuning, peaks between trials, or the probability of a
pulsar/correct period. Results state these assumptions. Legacy
`peak_confidence` is null and `confidence_thresholds` empty; use
`false_alarm_method`, `false_alarm_probability_upper_bound` and
`false_alarm_thresholds`. Fewer than four samples gives no bound. The
[M2 acceptance record](analysis/pulsar-candidates-confidence.md) gives the
derivation, independent checks and numerical Nyquist correction.

Peak probabilities use directly fitted `peak_residual_fraction` (RSS/TSS),
which avoids losing the residual when power rounds to its maximum. If that
residual falls below estimated solver resolution the probability is null;
power thresholds that cannot be represented below the maximum are omitted.
`false_alarm_resolution_limited` and its warning disclose either case. This
is a numerical resolution policy, not certified floating-point interval
arithmetic. Read the returned bound rather than deriving one from rounded
power. New artifacts identify `false_alarm_statistic=residual_fraction`;
earlier Gaussian-bound artifacts need recomputation, and their saved levels
are drawn as uncalibrated legacy thresholds.

### What a blind search actually achieves

B0329+54 is the **only** one of the five bundled scans where this works with
default settings (remeasured 2026-10-21). Compared against the curated periods
and the recorded ATNF values beside the scans; no new live ATNF query was
needed for this check:

| Scan | Curated difficulty | `S1400` | Blind search result | Fold at curated `P0` |
| --- | --- | --- | --- |
| B0329+54 | Easy | 203 mJy | matches reference within 0.015% | 316σ |
| B1133+16 | Lightly Challenging | 20 mJy | ~2.18 s — baseline candidate | 17.7σ |
| B1933+16 | More Challenging | 58 mJy | ~2.18 s — baseline red noise | 7.5σ |
| B2021+51 | Lightly Challenging | 27 mJy | ~2.13 s — baseline candidate | 4.9σ |
| B2045−16 | Most Challenging | 22 mJy | ~1.98 s — unsupported candidate | 5.4σ |

Only the bright source matches at these defaults. This is a result for these
scans and grids, not a general instrument sensitivity limit. The new lower
bound changes which trial periods are sampled; the old mean-spacing grid
landed on 60 Hz for B1133 and B2045. Consequences for callers:

1. **Conditional noise bounds do not classify pulsars.** All five peaks have
   small Gaussian-noise bounds, including the four wrong periods. The legacy
   confidence labels are retired; real radio noise still violates the model.
2. **Inspect `peak_fold_snr` and the profile.** Its inherited cutoff of 8
   separates these five defaults empirically, and produces `peak_does_not_fold`
   below that cutoff. It is not a calibrated probability; periodic RFI can
   fold coherently too.
3. **Red-noise peaks move with `back_scale`; real periodicities do not.** On
   B1133+16 the spurious ~2.18 s peak appears at `back_scale` 3, 12 and 30 but
   the true 1.19 s period wins at 1 and 6. Varying it by rerunning
   `load_pulsar_lightcurve`, the stage that takes it, is the cheapest
   diagnostic available. These historical tuning observations used the earlier
   grid. Data-dependent retuning is outside the single-search noise bound.
4. **A reference period rescues a failed search, and costs the detection
   claim.** A catalogued period turns four of these five scans from failures
   into usable folds — offline for these five, via `curated_periods.json`, and
   through `search_atnf` for any other source. What it cannot do is stand in for
   the measurement.

B1933+16 resisted the recorded tuned searches. One possible limitation is
dispersion:
`DM = 158.6` smears its pulse across ~11% of its 359 ms period over the 80 MHz
effective band. It is the brightest of the four faint scans and still the
hardest in those tests. This does not prove that every search must fail or
that dedispersion would guarantee recovery. This pipeline has neither
dedispersion nor channelized intensity data with which to perform it.

### Measure first, check second

The curated period and ATNF's `P0` are **references to check a result against**,
not inputs to the pipeline. The ordering the tools and the system prompt state:

1. **Measure.** Run `compute_pulsar_periodogram`; read `peak_fold_snr` and
   `top_peaks`. This is the only evidence that does not depend on already
   knowing the answer.
2. **Compare.** Against stage 0's `curated_period_s`, or `search_atnf` for a
   source the curation does not cover. Agreement provides a cross-check; still
   inspect the fold and aliases. Report both numbers with their provenance.
3. **Retune, do not substitute.** On a disagreement, a low `peak_fold_snr`, or a
   `peak_does_not_fold` warning: rerun `load_pulsar_lightcurve` with a
   different `back_scale`, narrow `start`/`stop` away
   from the artifact, raise `steps`. The two artifacts on this data are
   0.016665 s (60.006 Hz mains) and a 2.1–2.2 s red-noise peak.
4. **Fall back, and say so.** Only once a retuned search has failed, fold at the
   reference period — and report that the period came from outside the data, so
   that profile's `pulse_snr` is not an independent period measurement.

The scans carry no period in-file, so a search without reference seeding
provides an independent period candidate. Neither a strong fold at that
candidate nor a reference-seeded fold alone proves a pulsar detection. Record
the period's origin, profile, alias checks and noise-model limitations.

Expect step 4 on the four faint scans. Reaching it is an ordinary outcome for
60 seconds on a 20 m dish, and reporting it plainly is the point.

---

## 4b. Plotting

`plot_pulsar` renders any stage's artifact as a PNG, choosing the chart from
the columns it finds (`time_s` → light curve, `period_s` or `frequency_hz` plus
`power` → periodogram,
`phase_s` → folded). It sits beside the pipeline rather than in it: nothing
downstream consumes a plot.

| Chart | Axes | Series |
| --- | --- | --- |
| Light curve | Time (s) / Intensity, linear | Polarization XX, Polarization YY |
| Period spectrum | Period (s) / Power, **logarithmic** | selected channel, "Global Maxima" marker in seconds, three dashed false-alarm lines |
| Frequency spectrum | Frequency (Hz) / Power, **linear** | selected channel, "Global Maxima" marker in hertz, three dashed false-alarm lines |
| Folded | Time (s) / Intensity, linear | Polarization XX, Polarization YY, and Difference + Sum **hidden by default** |

The base chart configuration is ported from Astromancer to
`algorithms/pulsar/charts.py`. MARS adapts the spectrum labels and axis to the
saved data: `channel=sum` is **Sum**, `source1` is **Polarization XX**, and
`source2` is **Polarization YY**. New spectrum ECSV artifacts record `channel`
alongside `freq_mode`, and their coordinate column carries an Astropy unit
(`s` or `Hz`). Standard-format single-flux spectra use **Data** for either
permitted selection (`sum` or `source1`), preserving that selection in metadata
without claiming an XX/YY polarization. Plot results report `channel` and `mode`;
the saved column name determines the coordinate even when an older artifact
lacks `freq_mode` or contains a stale flag. Missing, non-string or unrecognized
channel metadata produces an **Unknown channel** legend and
`unknown_spectrum_channel` warning. Recompute an older spectrum to recover its
channel identity; it cannot be inferred from the saved powers.

The hidden folded series, folded x extent and peak styling retain the ported
defaults. Current false-alarm lines name the Gaussian noise model and its bound;
historical confidence levels are drawn as uncalibrated legacy thresholds with
`legacy_confidence_uncalibrated`. M2 also corrects candidate units, sampling
defaults and significance as described in §4. The
`docs/extraction.md` entry that listed the Highcharts components as "left
behind as UI" is superseded for the parts that decide *what* is drawn; the
widget plumbing (boost thresholds, tooltips, export buttons) was not ported.

**The periodogram plot is the diagnostic worth reaching for.** §4 explains that
four of five bundled scans return a confident artifact rather than the pulsar;
on the plot that is immediate — the peak sits at 0.0167 s with a forest of
narrow interference spikes, and the false-alarm lines lie far below everything.
For B0329+54 the same plot shows the fundamental at 0.7148 s marked as Global
Maxima with its harmonic comb at P/2, P/3, P/4… receding to the left.

---

## 5. Where the output goes

Every stage writes into `<artifact dir>/pulsar/`, where the artifact directory
is `$MARS_ARTIFACT_DIR` if set and `./artifacts` otherwise, **resolved to an
absolute path at import**. Returned `artifact.path` values are therefore always
absolute — a caller can change directory or hand the path to another process.

Names are stage-consistent and derived from the scan's `SRC_NAME`:

```text
artifacts/pulsar/
  psr_b0329_54_lightcurve.ecsv            # stage 1
  psr_b0329_54_periodogram.ecsv           # stage 2
  psr_b0329_54_folded.ecsv                # stage 3
  psr_b0329_54_sonification_folded.wav    # stage 4, with a period
  psr_b0329_54_sonification_lightcurve.wav# stage 4, without one
  psr_b0329_54_folded_plot.png            # plot_pulsar
```

A rendered sample is committed at
`docs/examples/psr_b0329_54_sonification.wav` — produced by the agent loop, not
a script; see that folder's README for the tool calls it chose. It is the only
generated file in the repository.

Pass `output_name` to override the stem, or `subdir` to change the folder.
Existing files are never overwritten: a second run appends `_1`, `_2`, ….
`artifacts/` is in `.gitignore`.

**These are deliberately not upstream's filenames.** Astromancer downloads
under its *chart* titles — `getChartTitle()` gives
`psr_b0329_54_2025-08-11T13:44:32.050_prefolded_light_curve` and
`getPeriodFoldingTitle()` gives `..._folded_light_curve`. Two problems for a
tool: the browser download filename was a UI concern (split off into
`downloadWav()` at extraction, not algorithm), and using the chart title for a
folded render names it "prefolded", which states the opposite of the truth. All
three upstream titles are still parsed and kept on `PulsarObservation`
(`title`, `periodogram_title`, `folding_title`) for anyone reproducing them.

---

## 6. Result contracts

Small typed models in `tools/models.py`, each carrying an `ArtifactRef` rather
than inline arrays, per `docs/tool-architecture.md`:

| Stage | Model | Artifact |
| --- | --- | --- |
| 1 | `PulsarLightCurve` | `.ecsv` — `time_s`, `source1`, `source2?` + header metadata |
| 2 | `PulsarPeriodogram` | `.ecsv` — `period_s`/`frequency_hz`, `power` |
| 3 | `PulsarFoldedProfile` | `.ecsv` — `phase_s`, `source1`, `source2?`, `difference?`, `sum?` |
| 4 | `PulsarSonification` | `.wav` — 16-bit PCM, stereo when both polarizations are present |

All four share `PulsarObservationInfo`, so the source name, sample counts and
background-subtraction settings read the same at every stage.

Failures are returned as `errors` on the model, never raised, so an agent loop
can report them and continue.

### 6a. Bounded input and computation

Stages 1–4 reject unsafe requests with `invalid_input` and no artifact. These
limits are checked before the relevant expensive loops or output allocations:

| Boundary | Limit / required input |
| --- | --- |
| Scan or light-curve artifact | 16 MiB file; 100,000 samples per vector |
| Background subtraction | Ordered finite times, positive finite `back_scale`; at most 20,000,000 samples summed across running-median windows |
| Folding | Positive finite period; finite phase/calibration; 1–10,000 bins; at most 100,000 repeated-subtraction iterations and 100,000,000 sample-iterations |
| Periodogram | At least three distinct finite times; finite positive variance; 1–200,000 steps; at most 200,000,000 sample-grid units; finite progressing grid and spectral products |
| Sonification | Positive finite speed/durations, finite calibration; integer sample rate 1–192,000 Hz; 1–4,000,000 output frames **and** at most 600 seconds; at most 4,000,000 interpolated points per channel |

The limits compose: 600 seconds is not available at every rate. At the default
44,100 Hz, the frame budget permits approximately 90.7 seconds; the default
60-second render is within it. Reduce duration/rate or narrow the spectrum
grid/window when a limit is hit. Do not blindly retry the same invalid request.
Constant, all-NaN, too-short or degenerate-time spectra are failures, not
successful measurements. The existing sonification window still drops NaN
rows; other calculation inputs must be finite. Accepted-input arithmetic and
the documented upstream quirks remain unchanged.

Discovery reads at most 256 comment lines and 65,536 decoded characters per
header (including its first non-comment line). A listing skips unreadable or
disappearing files with `scan_unreadable` warnings and keeps readable scans.
Direct-path read/stat failures return `read_failed`, and oversized headers
return `parse_error`; check both warnings and errors before choosing a scan.

These are local-work acceptance limits, not wall-clock cancellation, an OS
sandbox or general plot/archive budgets. The remaining boundaries are tracked
under M1/MCP-01 and PUL-07 in the master continuation plan.

---

### 6b. Public and Python-only controls (M3, 2026-10-22)

Every control the Python functions take is either public (in the registered
schema, so the agent loop and MCP callers can pass it) or Python-only (a direct
Python caller can pass it; a registered caller cannot, because undeclared
arguments are refused before dispatch). `tests/test_m3_pulsar_controls.py`
pins both lists, and fails if a new parameter is added to neither.

| Control | Public on | Python-only on | Why |
| --- | --- | --- | --- |
| `back_scale`, `subtract_background` | `load_pulsar_lightcurve` | periodogram, fold, sonify, plot | Background is subtracted once, at ingest. Later stages and the plotter apply these only when handed a raw scan; with a stage-1 artifact they did nothing, silently. `sonify_pulsar` exposed them anyway and so is narrowed. In Python they default to "not given". A direct call whose setting differs from what the artifact records (`background_subtracted`, `back_scale_s`) gets `background_settings_ignored`, naming the recorded setting. It is a warning rather than a rejection so existing direct callers keep working. |
| `x_label`, `y_label` | -- | `plot_pulsar` | Axis labels come from upstream's charts and say which channel and unit is drawn (M2 corrects them). A caller-chosen label could relabel a channel or swap seconds and hertz. |
| `dpi`, `figsize` | -- | `plot_pulsar` | Presentation only; fixed sizes keep plot artifacts bounded. |
| `cal` | -- | fold, sonify | Gain on the second polarization (upstream's balance slider). A caller has no measurement to set it from. |
| `phase` | fold | sonify | On the fold it shifts the profile so a pulse straddling the wrap reads clearly; on the looped audio it only moves where the loop starts. |
| `max_input_seconds`, `sample_rate` | -- | sonify | Upstream's fixed 60 s input window and 44.1 kHz rate; widening them works against the PUL-02 bounds (§6a). |

`subdir` (all stages) and `directory` (scan listing) are server-side destination
and data-root keywords, not controls. Retuning a blind search therefore means
rerunning `load_pulsar_lightcurve` with a different `back_scale`. The stage-2
description, the shipped prompt and the skill say so; they used to say "vary
back_scale" on a stage that has no such parameter.

## 7. Not covered

- **No dedispersion.** These are single-band continuum scans; the pipeline
  never sees a frequency axis, so dispersion measure plays no part.
- **No barycentric correction.** Periods are topocentric, which is why they
  differ from an ATNF `P0` in the fourth decimal.
- **No period uncertainty.** The periodogram reports a grid peak, not a fitted
  period with an error bar. Refine by re-running with a narrow `start`/`stop`
  and more `steps`. The curated period stage 0 reports carries no error bar
  either — it is a transcribed literature value, and it is barycentric while
  the scans are topocentric.
- **No curated period beyond the bundled five.** `curated_periods.json` covers
  the scans in this repository and nothing else. A scan from elsewhere resolves
  with `curated_period_s` null, and its period has to be measured or fetched
  from ATNF.
- **`sonificationBrowser` is not ported** — it drives an `AudioContext`, which
  a file-writing tool has no use for. Its retired extraction remains in git
  history.

---

## 8. Open bugs and the plotting-tools review

Known tool-correctness bugs in `tools/pulsar.py`, and the review of the pulsar
plotting tools, live in
[`analysis/pulsar-pipeline-review.md`](analysis/pulsar-pipeline-review.md) — kept
separate so this document stays a description of the pipeline as designed.
