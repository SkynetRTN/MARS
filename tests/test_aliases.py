"""The Kepler command names survive one pre-release as aliases of the MARS ones.

``docs/working/mars-rebrand.md`` §6.3: each old command names its successor on
stderr -- ``mars-mcp``'s stdout is the protocol -- and then runs it unchanged.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from tools import aliases

_PYPROJECT = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
)
_SCRIPTS = _PYPROJECT["project"]["scripts"]

#: old command -> (alias function, new command, the target it must forward to)
_ALIASES = {
    "kepler": ("kepler", "mars", ("tools.tui", "launch")),
    "kepler-mcp": ("kepler_mcp", "mars-mcp", ("tools.mcp.__main__", "main")),
    "kepler-bench": ("kepler_bench", "mars-bench", ("tools.bench.cli", "main")),
}


def test_the_distribution_is_skynet_mars():
    assert _PYPROJECT["project"]["name"] == "skynet-mars"


@pytest.mark.parametrize("old", sorted(_ALIASES))
def test_each_old_command_is_declared_as_its_alias(old):
    function, new, (module, attr) = _ALIASES[old]
    assert _SCRIPTS[old] == f"tools.aliases:{function}"
    assert _SCRIPTS[new] == f"{module}:{attr}"


@pytest.mark.parametrize("old", sorted(_ALIASES))
def test_each_alias_names_its_successor_on_stderr_and_forwards(old, monkeypatch, capsys):
    import importlib

    function, new, (module, attr) = _ALIASES[old]
    monkeypatch.setattr(importlib.import_module(module), attr, lambda: 7)

    assert getattr(aliases, function)() == 7
    out, err = capsys.readouterr()
    assert out == ""
    assert f"renamed to `{new}`" in err
    assert aliases.REMOVED_AFTER in err
