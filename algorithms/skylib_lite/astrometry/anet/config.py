"""Configuration for the (optional) astrometry.net subprocess backend.

v2 note: the in-process SWIG engine is gone. The backend now shells out to the
system ``solve-field`` binary, so configuration is about *where* that binary and
its index files live — not an in-process engine handle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

from ..limits import DEFAULT_SOLVER_TIMEOUT_S, normalize_solver_timeout

@dataclass
class AstrometryNetConfig:
    #: Directory or directories containing astrometry.net index files. Recognized
    #: naming conventions (no renaming required): the standard ``index-*.fits``,
    #: vendor-prefixed ``*-index-*.fits`` (e.g. UCAC5 ``ucac5-index-00-00.fits``),
    #: and suffixless ``index-NNN`` (e.g. TYCHO2 ``index-205``). If None, the
    #: backend falls back to the SKYLIB_ASTROMETRYNET_INDEX_PATH (then
    #: SKYLIB_ANET_INDEX_ROOT) environment variable, os.pathsep-separated.
    #: Directories are validated at solve time; those that are missing or hold no
    #: recognized index files are dropped.
    index_path: Optional[Union[str, Sequence[str]]] = None
    #: Override the ``solve-field`` executable (absolute path or a name on PATH).
    #: If None, it is resolved from SKYLIB_ASTROMETRYNET_SOLVE_FIELD /
    #: SKYLIB_ANET_SOLVE_FIELD and then ``shutil.which("solve-field")``.
    solve_field_path: Optional[str] = None
    #: CPU limit plus a finite outer wall-clock backstop. None selects 300 s;
    #: explicit limits must be 1–900 s. Not a whole-call deadline (WCS-21).
    timeout_s: Optional[float] = DEFAULT_SOLVER_TIMEOUT_S
    #: Extra raw arguments appended to the solve-field command line.
    extra_args: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self.timeout_s = normalize_solver_timeout(self.timeout_s)


__all__ = ["AstrometryNetConfig"]
