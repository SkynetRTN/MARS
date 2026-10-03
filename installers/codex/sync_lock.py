"""Lock the Codex plugin to the versions the repository tests.

The plugin's ``uv.lock`` is resolved on its own, so left alone it picks newer
releases than the root ``uv.lock`` that CI's parity suite runs against. This
re-locks every package the two share at the root's version.

    python installers/codex/sync_lock.py

Run it from the repository root after bumping the pin, instead of ``uv lock``.
``tests/test_codex_plugin.py`` fails while the locks disagree.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_LOCK = HERE.parents[1] / "uv.lock"


def _versions(lock: Path) -> dict[str, str]:
    """Every locked package but skynet-mars itself: the plugin pins the
    published release, which trails the repository's version."""
    packages = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    return {p["name"]: p["version"] for p in packages if p["name"] != "skynet-mars"}


def main() -> int:
    subprocess.run(["uv", "lock"], cwd=HERE, check=True)
    root, ours = _versions(ROOT_LOCK), _versions(HERE / "uv.lock")
    pins = [f"--upgrade-package={name}=={root[name]}" for name in ours if name in root and root[name] != ours[name]]
    if pins:
        subprocess.run(["uv", "lock", *pins], cwd=HERE, check=True)
    ours = _versions(HERE / "uv.lock")
    drift = {name: (root[name], ours[name]) for name in ours if name in root and root[name] != ours[name]}
    if drift:
        print(f"still differs from the root lock: {drift}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
