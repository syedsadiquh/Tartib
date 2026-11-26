"""Schema guarantees that live in Postgres, not in the service layer (DB-01).

These run against the real migration (see ``tests/conftest.py``), so a CHECK or an
exclusion constraint that autogenerate dropped fails here rather than in production.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from scheduler.models import OWNER_ID, Calendar, Habit, Placement, PlanRun

BASE = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)


def _calendar(session: Session) -> Calendar:
    calendar = Calendar(
        user_id=OWNER_ID,
        google_calendar_id="cal-tasks",
        summary="Tasks & Todos",
        color="#1d76db",
        access_role="owner",
    )
    session.add(calendar)
    session.flush()
    return calendar


def _placement(
    session: Session, calendar: Calendar, *, start: datetime, end: datetime, pinned: bool = False
) -> Placement:
    return Placement(
        user_id=OWNER_ID,
        ref_type="task",
        ref_id=calendar.id,  # any uuid; the column is deliberately polymorphic
        kind="task_chunk",
        local_date=start.date(),
        start_at=start,
        end_at=end,
        calendar_id=calendar.id,
        pinned=pinned,
        created_by="engine",
        updated_by="engine",
    )


def test_overlapping_active_placements_are_rejected(db_session: Session) -> None:
    calendar = _calendar(db_session)

    db_session.add(_placement(db_session, calendar, start=BASE, end=BASE + timedelta(hours=1)))
    db_session.commit()

    db_session.add(
        _placement(
            db_session,
            calendar,
            start=BASE + timedelta(minutes=30),
            end=BASE + timedelta(minutes=90),
        )
    )
    # The exclusion constraint is DEFERRABLE INITIALLY DEFERRED: it fires at COMMIT.
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_overlapping_placement_is_allowed_when_one_is_pinned(db_session: Session) -> None:
    calendar = _calendar(db_session)

    db_session.add(_placement(db_session, calendar, start=BASE, end=BASE + timedelta(hours=1)))
    db_session.add(
        _placement(
            db_session,
            calendar,
            start=BASE + timedelta(minutes=30),
            end=BASE + timedelta(minutes=90),
            pinned=True,
        )
    )
    db_session.commit()  # must not raise


def test_second_proposed_plan_run_is_rejected(db_session: Session) -> None:
    def plan_run(status: str = "proposed") -> PlanRun:
        return PlanRun(
            user_id=OWNER_ID,
            trigger="manual",
            status=status,
            input_hash="deadbeef",
            requested_by="user",
        )

    db_session.add(plan_run())
    db_session.commit()

    db_session.add(plan_run())
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_habit_min_min_above_ideal_min_is_rejected(db_session: Session) -> None:
    db_session.add(
        Habit(
            user_id=OWNER_ID,
            name="Gym",
            weekdays=[1, 3, 5],
            ideal_min=60,
            min_min=90,  # violates CHECK (min_min <= ideal_min)
            not_before=time(6, 0),
            not_after=time(9, 0),
            priority_key="fixed",
            compressible=True,
            active_from=date(2026, 11, 26),
            created_by="user",
            updated_by="user",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
