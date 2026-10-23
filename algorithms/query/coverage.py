"""Operation-scoped catalog notices; no mutable state on shared backends."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import logging


@dataclass(frozen=True)
class QueryNotice:
    code: str
    message: str


_collectors: ContextVar[tuple[list[QueryNotice], ...]] = ContextVar("catalog_notices", default=())
logger = logging.getLogger(__name__)


@contextmanager
def collect_query_notices():
    notices: list[QueryNotice] = []
    token = _collectors.set((*_collectors.get(), notices))
    try:
        yield notices
    finally:
        _collectors.reset(token)


def note_query_issue(code: str, message: str) -> None:
    notice = QueryNotice(code, message)
    logger.warning("%s: %s", code, message)
    for collector in _collectors.get():
        if notice not in collector:
            collector.append(notice)


def note_row_limit(catalog: str, raw_rows: int, limit: int | None, *, sort=()) -> None:
    """A response reaching the cap may be incomplete, even if mapping drops rows."""
    if limit is None or limit <= 0 or raw_rows < limit:
        return
    ordering = (f" Requested ordering: {', '.join(sort)}; a magnitude-sorted cap "
                "can favor bright, possibly saturated stars.") if sort else " The subset has no completeness or unbiased-sampling guarantee."
    note_query_issue("catalog_rows_capped",
                     f"{catalog}: {raw_rows} raw rows reached the {limit}-row limit; "
                     "catalog coverage may be incomplete." + ordering)


def note_early_stop(catalog: str, rows: int, remaining: list[str]) -> None:
    if remaining:
        note_query_issue("catalog_fallback_not_exhausted",
                         f"Stopped after {catalog} returned {rows} source(s); "
                         f"did not query {', '.join(remaining)}. A nonempty catalog "
                         "does not establish a sufficient calibration sample.")
