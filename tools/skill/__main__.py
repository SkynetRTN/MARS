"""``python -m tools.skill`` renders every copy of the skill; ``--check`` reports drift."""

from __future__ import annotations

import argparse
import sys

from tools.skill import RENDERED_COPIES, REPOSITORY_COPY, check_repository_copy, write_repository_copy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.skill",
        description="Render the MARS skill source into "
        + " and ".join(str(target) for target in RENDERED_COPIES)
        + ".",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Write nothing; exit 1 if any rendered copy is out of date.",
    )
    args = parser.parse_args(argv)

    from tools.paths import is_checkout

    if not is_checkout():
        print(
            "python -m tools.skill renders the checkout's copies, skills/mars-tools/ "
            "and installers/codex/skills/mars-tools/, and only runs in a checkout: "
            "this is an installed package, and writing "
            "there would put files into site-packages.",
            file=sys.stderr,
        )
        return 2

    root = REPOSITORY_COPY.parents[1]
    if args.check:
        drift = [
            (target / name).relative_to(root).as_posix()
            for target in RENDERED_COPIES
            for name in check_repository_copy(target)
        ]
        for name in drift:
            print(f"stale: {name}", file=sys.stderr)
        return 1 if drift else 0

    for target in RENDERED_COPIES:
        for name in write_repository_copy(target):
            print(f"rendered: {(target / name).relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
