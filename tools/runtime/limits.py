"""Finite operational budgets for trusted-local MCP calls (MCP-01/AUD-03)."""

from dataclasses import dataclass
import math
import os


@dataclass(frozen=True)
class CallLimits:
    timeout_s: float = 600
    memory_bytes: int = 4 * 1024**3
    work_bytes: int = 256 * 1024**2
    download_bytes: int = 512 * 1024**2
    log_bytes: int = 1024**2
    reply_bytes: int = 4 * 1024**2
    input_bytes: int = 1024**2
    files: int = 10_000
    retained_bytes: int = 5 * 1024**3

    def __post_init__(self):
        if isinstance(self.timeout_s, bool) or not math.isfinite(self.timeout_s) or not 0 < self.timeout_s <= 1800:
            raise ValueError("MCP call timeout must be finite and in (0, 1800] seconds.")
        for name in self.__dataclass_fields__:
            if name == "timeout_s":
                continue
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer budget.")

    @classmethod
    def from_environment(cls):
        raw = os.environ.get("MARS_MCP_CALL_TIMEOUT_S")
        return cls(timeout_s=600 if raw is None else float(raw))
