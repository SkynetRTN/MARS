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

**Disposition (maintainer, 2026-11-10).** HR fits are sensitive and hard
to do, so their settings must be adjustable, by the agent in its tool-call
loop, to bring a fit as close to the catalog values as it can. The threshold
is therefore a setting, not a fixed rule: `track_max_gap_mag` on
`fit_and_compare_hr_diagram`, default 0.5 mag, so a fit at the defaults is
unchanged. Each result reports the `fit_settings` it used, including the
ages scanned. The tool description and the skill's HR guide tell the agent
to re-run the fit on the same members CSV, to say which settings it changed,
and that a fit tuned toward the literature values does not independently
confirm them. The change is `feature/hr-fit-track-gap` (`28be2e6`, from
`main`), recorded in `extraction.md`; a slow test pins M67's move at 0.5 and
1.0 mag.

Reproduce: set `tools.config.ISOCHRONE_DIR`, stub
`tools.hr_diagram._fetch_literature_params`, and call
`tools.hr_diagram.fit_and_compare_hr_diagram(members_csv, "M67",
max_error=0.2, track_max_gap_mag=X)`. Without the setting, patch
`algorithms.hrdiagram_py.hrfit._resample_track` with
`functools.partial(original, max_gap=X)` instead.

## 2. Checks on the release candidate

The candidate is `main` at `4ec3e9c` (M5 merged) plus this branch. Since
`4ec3e9c` the branch changes Markdown files and one URL in `pyproject.toml`:
no Python, workflow or lockfile. The code CI tested at `4ec3e9c` is therefore
the code here. The release also takes the `track_max_gap_mag` change (§1),
which does change code; it was checked on its own branch (the last two rows)
and gets CI on its own pull request.

| Check | Where it ran | Result |
|---|---|---|
| Supported suites on Python 3.12 and 3.13 (`uv run --locked --extra mcp pytest`, after the MCP tests without the extra) | CI on `main` at `4ec3e9c`: run 42713731317 (push, 2026-11-09) and PR #136 | passed |
| Packaging on 3.12 and 3.13: build, `twine check --strict`, `check_dist.py`, a clean install with `[mcp]`, and `mars-mcp self-test` outside a checkout | the same runs | passed |
| Native runtime containment on `macos-latest` and `windows-11-arm` | the same runs | passed |
| Secret scan (gitleaks over the tree and full history) | run 42713731549 | passed |
| Workflow safety (actionlint, zizmor) | run 42713731297 and PR #136 | passed |
| Full suite on the candidate, Python 3.13.14, locked, with `[mcp]` | this host, at `e3456d9` | 5,178 passed, 96 skipped, no failures (648 s) |
| Native plate solving with the host's solver data (`MARS_CATALOG_DIR=/srv/agents/catalogs`, the M5 parity index): `test_wcs_solution.py`, `test_wcs_solve_tool.py`, `test_m5_solver_controls_investigation.py` | this host | 257 passed, none skipped (128 s) |
| The MCP tests without the SDK (CI's first step) | this host, separate environment | 241 passed, 21 skipped |
| Wheel and sdist built from a clean worktree at `e3456d9`: `twine check --strict` (6.2.0) and `check_dist.py` | this host | passed |
| Clean install of the wheel with `[mcp]`, and `mars-mcp self-test` run outside the checkout | this host | passed: B0329+54 measured at 0.71462 s against the curated 0.71452 s, folded at 218.5σ |
| The skill `install-skill` writes from the wheel, against `skills/mars-tools/`; `python -m tools.skill --check` | this host | identical; no drift |
| Full suite on `feature/hr-fit-track-gap` (`28be2e6`, from `main`), Python 3.13.14, locked, with `[mcp]` | this host, clean worktree | 5,181 passed, 100 skipped, no failures (775 s): the 7 new tests pass, and 4 benchmark checks that read the untracked run records in `artifacts/bench/` skip in a clean worktree |
| The MCP tests without the SDK on `28be2e6` (CI's first step) | this host, separate environment | 241 passed, 21 skipped |

The local clean install resolved its dependencies from the uv cache, as a
clean runner resolves them from PyPI, not from `uv.lock`. No added or changed
line names an API-key variable outside the secret scan's allowlist.

**Not rerun.** The release workflow's last dry run (run 40611174066,
`workflow_dispatch`, 2026-10-28) was on M4's branch and predates M5. Its
installed-wheel, bundle and Claude Desktop extension checks on macOS and
Windows on ARM have not run at the candidate. A tag push runs them again
before anything is published.

## 3. Skipped external checks

By the maintainer's decision (2026-11-04), these are not run for this
release:

- the `network` live catalog and service tests (77 skipped in the local
  run, plus 3 live ADS cases that need `ADS_DEV_KEY`);
- the `model_api` live-provider tests;
- the live ADS tests after ADS becomes SciX on 2026-11-16;
- Codex in the ChatGPT app on a Mac, which stays untested.

The local full suite's other 15 skips are not external. Ten are native
plate-solving cases, skipped because the default suite withholds the host's
solver data; they pass when it is supplied (§2). One needs native Windows,
which CI's `windows-11-arm` job provides. Four are status checks for result
types that carry no errors.

## 4. Before the release

- **The final merged revision** is recorded when this branch merges.
- **CI on this branch's pull request.**
- **The release dry run, or the tag run, at that revision.** It repeats the
  installed-wheel, bundle and extension checks that predate M5.
- **A new version.** The candidate still says `0.1.0rc6`; `releasing.md`
  owns the bump.
- **The `track_max_gap_mag` change merges first** (§1), with CI on its own
  pull request. It is the candidate's only code change since `4ec3e9c`.

The outstanding user-visible limitations are listed in
[Known limitations](../limitations.md).
