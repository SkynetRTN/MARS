# Development and release maintenance

For contribution rules and checks, start with [CONTRIBUTING.md](../../CONTRIBUTING.md)
and [the test coverage guide](../../tests/README.md). The [architecture
references](../architecture/technical-summary.md) describe the current implementation.

| Need | Document |
| --- | --- |
| Cut a release, verify distributions or publish optional data | [Release procedure](releasing.md) |
| Find current release gates and dispositions | [Master continuation plan](plans/master-continuation-plan.md) |
| Find evidence behind a correction or decision | [Dated reviews and investigations](reviews/README.md) |
| Understand a completed implementation track | [Archive](archive/README.md) |

M1–M6 and stable `0.1.0` preparation are merged through
[PR #139](https://github.com/SkynetRTN/MARS/pull/139), at `8a91523`.
Publication remains a separate maintainer action. The master stays active until
merged/tagged revision checks and publication outcomes are recorded.

Keep current plans in `plans/`, dated findings in `reviews/`, and completed
tracks or task recipes in `archive/`. The [documentation map](../README.md)
defines their lifecycle. Implementation scratch and agent-session artifacts
belong outside the documentation tree.
