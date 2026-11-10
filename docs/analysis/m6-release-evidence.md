# M6: release evidence

Evidence for the [master plan](../working/master-continuation-plan.md#m6-record-the-release-decision-and-its-limits)'s
*Release evidence* item, gathered on `docs/m6-release-decision` after M5
merged to `main` as PR #136 (`4ec3e9c`, 2026-11-09). The scope decisions
are in [their own record](m6-scope-decisions.md). The user-visible
limitations are in [Known limitations](../limitations.md).

Host: Fedora 44, Linux aarch64, 8 cores, Python 3.13 (locked environment).

## 1. The HR fit's track-joining rule

M5 handed this to M6 as a release question "requiring measurement or an
explicit disposition". The fit resamples each Girardi track before scoring
stars against it, joining consecutive points only when they are at most
`TRACK_MAX_GAP_MAG` = 0.5 mag apart (`algorithms/hrdiagram_py/hrfit.py:255`).
The grid has no phase labels, so the rule stands in for phase breaks.

**Measured 2026-11-10.** The shipped `fit_and_compare_hr_diagram` was run on
M67's recorded members (`tests/fixtures/hrdiagram_m67/members.csv`, 548
stars, `max_error=0.2`, the default ±0.3 dex age window). The tracks were the
operator grid at `/srv/agents/isochrones`, and the literature values were
stubbed as the M5 test stubs them (log age 9.60, 0.889 kpc, E(B−V) 0.023).
Only the joining threshold was varied:

| Joining threshold | Distance (kpc) | E(B−V) | log age | Reduced cost |
|---|---|---|---|---|
| 0.25 mag | 0.8678 | 0.0502 | 9.50 | 3.874 |
| **0.5 mag (shipped)** | **0.8521** | **0.0352** | **9.60** | **3.316** |
| 0.75 mag | 0.8599 | 0.0441 | 9.55 | 3.025 |
| 1.0 mag | 0.8599 | 0.0441 | 9.55 | 3.025 |
| 2.0 mag | 0.8599 | 0.0441 | 9.55 | 3.025 |
| join every point | 0.8599 | 0.0441 | 9.55 | 3.025 |

The fixture's own float32 copies of the tracks give the same results to four
decimals. Each fit took about 19 s.

**Why 0.75 mag and above agree.** On the tracks in the window (log age
9.50–9.65), the steps between 0.5 and 0.75 mag fall in two places. The grid
samples the faint main sequence (M_G ≈ 6.9–13.4) every 0.50–0.60 mag. The
rest are thermally pulsing AGB steps near M_G −2. The shipped rule therefore
leaves stretches of the main sequence, a single evolutionary phase, unjoined.
M4 found the same on M67's fitted track, where 27 members between M_G 6.94
and 7.48 are scored against the two end points only. Joining the AGB steps
as well changes nothing on M67, which has few members there.

**What this establishes.** On M67, the shipped rule moves the fitted age by
one grid step (log 9.55 to 9.60, about 12%) and lowers E(B−V) by 0.009 mag
and the distance by 0.9%, compared with any rule that joins the main
sequence. Those shifts are about the size of the fit's own offsets from the
stubbed literature values (−4.1% in distance, +0.012 in E(B−V)). The shipped
fit reports no parameter uncertainty (`parameter_uncertainty` is always
null), so it gives no error bar to compare them with.

A lower reduced cost alone does not show that a rule is right. In this case
it comes from joining in-phase main-sequence points, which is the
interpretation offered here, not a validated result. One cluster does not
establish the size of the effect elsewhere.

**Disposition:** the maintainer's. The two options are to keep 0.5 mag and
disclose it, as [Known limitations](../limitations.md) now does, or to change
the threshold. A change alters fitted results, and needs its own tests and
an entry in `extraction.md`.

Reproduce: patch `algorithms.hrdiagram_py.hrfit._resample_track` with
`functools.partial(original, max_gap=X)`, set `tools.config.ISOCHRONE_DIR`,
stub `tools.hr_diagram._fetch_literature_params`, and call
`tools.hr_diagram.fit_and_compare_hr_diagram(members_csv, "M67",
max_error=0.2)`.
