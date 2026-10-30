"""Operation-scoped disclosures for retained numerical behavior."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import logging


@dataclass(frozen=True)
class NumericalNotice:
    code: str
    message: str


_collectors: ContextVar[tuple[list[NumericalNotice], ...]] = ContextVar("numerical_notices", default=())
logger = logging.getLogger(__name__)


@contextmanager
def collect_numerical_notices():
    notices: list[NumericalNotice] = []
    token = _collectors.set((*_collectors.get(), notices))
    try:
        yield notices
    finally:
        _collectors.reset(token)


def note_numerical_issue(code: str, message: str) -> None:
    notice = NumericalNotice(code, message)
    logger.warning("%s: %s", code, message)
    for collector in _collectors.get():
        if notice not in collector:
            collector.append(notice)
