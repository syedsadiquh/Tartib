"""clock.now() is the single source of wall time (ARCH §3)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone

import pytest

from scheduler import clock


@pytest.fixture(autouse=True)
def _reset_clock() -> Iterator[None]:
    clock.reset()
    yield
    clock.reset()


def test_now_is_tz_aware_utc() -> None:
    assert clock.now().tzinfo is not None
    assert clock.now().utcoffset() == timedelta(0)


def test_set_fixed_freezes_and_normalises_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    frozen = datetime(2026, 11, 22, 13, 0, tzinfo=ist)
    clock.set_fixed(frozen)

    assert clock.now() == datetime(2026, 11, 22, 7, 30, tzinfo=UTC)
    assert clock.now() is clock.now()
    assert clock.now().utcoffset() == timedelta(0)


def test_set_fixed_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="tz-aware"):
        clock.set_fixed(datetime(2026, 11, 22, 13, 0))


def test_reset_returns_to_wall_clock() -> None:
    clock.set_fixed(datetime(2020, 1, 1, tzinfo=UTC))
    clock.reset()
    assert clock.now().year >= 2026
