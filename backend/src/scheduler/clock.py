"""The only module that reads wall time (01-architecture §3).

Everything else takes ``now`` as a parameter or calls :func:`now`. Tests freeze it
with :func:`set_fixed` and restore it with :func:`reset`.
"""

from __future__ import annotations

from datetime import UTC, datetime

_fixed: datetime | None = None


def now() -> datetime:
    """Current instant, always tz-aware UTC."""
    if _fixed is not None:
        return _fixed
    return datetime.now(UTC)


def set_fixed(value: datetime) -> None:
    """Freeze the clock at ``value``. Naive datetimes are rejected."""
    if value.tzinfo is None:
        raise ValueError("set_fixed() requires a tz-aware datetime")
    global _fixed
    _fixed = value.astimezone(UTC)


def reset() -> None:
    """Return to reading the real wall clock."""
    global _fixed
    _fixed = None
