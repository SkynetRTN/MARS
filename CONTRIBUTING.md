# Contributing

MARS (MCP Astronomy Research Suite) is an astronomy tool collection. Keep pull requests narrow and target
`main` unless a maintainer asks for a different base branch.

## Pull Requests

- Separate documentation, workflow, dependency, and behavior changes when practical.
- Do not commit API keys, local environment files, downloaded FITS products,
  archive dumps, generated plots, caches, or large astronomy datasets.
- Keep remote astronomy service calls out of default checks unless they are
  explicitly gated as live tests.
- Include provenance and bounded-output considerations when changing tool
  behavior.

## Local Checks

Run the smallest relevant checks before opening a PR:

```bash
uv sync
uv run pytest
python3 -m compileall tools algorithms
git diff --check
```

See `tests/README.md` for what the suite does and does not cover, and which
markers (`network`, `slow`, `solver_data`) gate the heavier checks.

## Documentation

Start with [the documentation map](docs/README.md). Keep user-facing guides in
`docs/guides/`, technical references in `docs/architecture/`, and maintainer
procedures and records in `docs/development/`. Keep only `README.md` at the
docs root. Agent-session scratch belongs outside the documentation tree.

The active [master continuation plan](docs/development/plans/master-continuation-plan.md)
owns release gates. Preserve completed task plans in `development/archive/plans/`
and implementation tracks in `development/archive/tracks/`, with dated status
annotations. Reviews and measurements remain dated evidence; navigation can
follow the current layout without rewriting historical results.

Tool-use guidance has one source in `tools/skill/source/`. Run
`uv run python -m tools.skill` after editing it, and commit the generated copies.

## Code Ownership

`.github/CODEOWNERS` marks the repository as maintainer-owned. Branch rules
should require Code Owner review for changes to `main`.
