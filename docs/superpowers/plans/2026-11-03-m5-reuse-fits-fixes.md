# M5 repeated-call and FITS-write fixes

**Goal:** Repair all six confirmed issues in the
[investigation](../../analysis/m5-repeated-calls-fits-writes.md), starting from
`472424e` on `feature/m5-geometry`, without worktrees.

**Contracts:** Astrometry's saturation override is call-local. Aperture
photometry owns its result table and retains original isophotal weights for
adaptive reuse; current measurement flags replace previous aperture flags,
while extraction flags survive. A new accepted WCS replaces detector lookup
references and preserves source observation/time-origin metadata in both
writers. Source caps apply independently of optional flux; existing sorting
and automatic parity conventions remain unchanged.

## Work and verification

- [x] WCS-28: convert the native shared-settings probe to require an unchanged
  caller and unchanged later saturation rejection; copy settings before the
  local override. Files: `algorithms/wcs/wcs.py`, first reuse-test block.
- [x] M5-REUSE-01/02: convert native adaptive/flag probes to correctness;
  preserve isophotal provenance across input/output reuse, copy caller arrays,
  clear only prior aperture failure bits. Cover signed/unsigned flags,
  extraction flags, repeated settings and failed-to-valid measurements.
  Files: `algorithms/skylib_lite/photometry/aperture.py`, reuse tests.
- [x] M5-WRITE-01/02: require accepted coordinates after full-HDU reopen,
  including the real staged public boundary, and preserve single/split source
  time-reference values/comments without conflicting default cards. Share
  writer policy where useful, retaining file concurrency/atomicity guards.
  Files: WCS header helpers/regex/writer, `tools/wcs.py`, FITS write tests.
- [x] WCS-26: convert actual missing-flux xylist output to require the source
  cap, retaining input order without brightness and existing finite-flux order.
  Cover empty/short input and unlimited settings. Files: anet backend,
  solver-control tests.
- [x] Observe each corrected regression fail before production changes; run
  focused/related and bounded native checks, then review combined changes.
- [x] Update report, extraction provenance, test map and master status. Finish
  all source/test/guidance edits before the full locked offline suite. Run
  compilation, guidance consistency and whitespace checks; commit/push the
  feature branch and attempt the shared-memory transaction workflow.

Completed validation: 123 offline regressions/controls plus four optional
native cases; 860 related passes (eight skips), 56 native-enabled control
passes, and independent review with no outstanding findings after the legacy
AXISCORR correction. Final locked suite: 4,664 passed, 94 skipped, 214 FITS
notices, no failures (422.62 seconds). Compilation, guidance consistency and
whitespace pass. First-call old fields remain bit-exact in five native modes.

The latent explicit-parity contract, injected nonfinite-flux behavior and
ancillary frame/SIP metadata gaps keep their documented investigation
dispositions; this work does not expose new solver preferences.
