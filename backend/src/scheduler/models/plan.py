"""Plan runs, orphans, suppressed changes and day overrides (02-data-model §2.8)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, uuid_pk


class PlanRun(Base):
    """One engine run. At most one ``running`` and one ``proposed`` row at a time."""

    __tablename__ = "plan_run"
    __table_args__ = (
        CheckConstraint(
            "trigger IN ('hourly','task_change','calendar_change','manual','agent',"
            "'prayed','skip','settings','restore')",
            name="trigger",
        ),
        CheckConstraint(
            "status IN ('running','proposed','applied','rejected','superseded','failed','empty')",
            name="status",
        ),
        Index(
            "plan_run_single_proposed",
            text("(true)"),
            unique=True,
            postgresql_where=text("status = 'proposed'"),
        ),
        Index(
            "plan_run_single_running",
            text("(true)"),
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    changes: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    flags: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    accepted_change_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), nullable=False
    )
    auto_applied: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[str | None] = mapped_column(Text)
    decided_auto_approved: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )


class CalendarOrphan(Base):
    """An app-owned Google event with no placement; removed only by a reviewed delete."""

    __tablename__ = "calendar_orphan"

    google_event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calendar.id", ondelete="CASCADE"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, server_default=text("''"), nullable=False)
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SuppressedChange(Base):
    """A change the user declined; blocks the same deterministic change for 24 h."""

    __tablename__ = "suppressed_change"

    change_id: Mapped[str] = mapped_column(Text, primary_key=True)
    plan_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_run.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DayOverride(Base):
    """D-21 "make time": a per-day widening or narrowing of the usable window."""

    __tablename__ = "day_override"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    earliest_block: Mapped[time | None] = mapped_column(Time)
    latest_block_end: Mapped[time | None] = mapped_column(Time)
    reason: Mapped[str] = mapped_column(Text, server_default=text("''"), nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
