"""Habits and their per-day occurrences (02-data-model §2.5)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import AttributionMixin, Base, TimestampMixin, uuid_pk


class Habit(TimestampMixin, AttributionMixin, Base):
    """A repeating commitment with a time window and a compression floor."""

    __tablename__ = "habit"
    __table_args__ = (
        CheckConstraint("array_length(weekdays, 1) >= 1", name="weekdays_present"),
        CheckConstraint("ideal_min > 0", name="ideal_min_positive"),
        CheckConstraint("min_min > 0", name="min_min_positive"),
        CheckConstraint("min_min <= ideal_min", name="min_within_ideal"),
        CheckConstraint("not_before < not_after", name="window_ordered"),
        CheckConstraint("state IN ('active','ended','archived')", name="state"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
    ideal_min: Mapped[int] = mapped_column(Integer, nullable=False)
    min_min: Mapped[int] = mapped_column(Integer, nullable=False)
    not_before: Mapped[time] = mapped_column(Time, nullable=False)
    not_after: Mapped[time] = mapped_column(Time, nullable=False)
    ideal_time: Mapped[time | None] = mapped_column(Time)
    priority_key: Mapped[str] = mapped_column(Text, nullable=False)
    compressible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    calendar_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calendar.id"))
    state: Mapped[str] = mapped_column(Text, server_default=text("'active'"), nullable=False)
    streak_current: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    streak_best: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    consecutive_skips: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    active_from: Mapped[date] = mapped_column(Date, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class HabitOccurrence(Base):
    """One row per due day; created lazily and unique per (habit, date)."""

    __tablename__ = "habit_occurrence"
    __table_args__ = (
        UniqueConstraint("habit_id", "date"),
        CheckConstraint("state IN ('scheduled','done','skipped','missed')", name="state"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    habit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("habit.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(Text, server_default=text("'scheduled'"), nullable=False)
    planned_min: Mapped[int | None] = mapped_column(Integer)
    actual_min: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    compressed_min: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    skip_batch_id: Mapped[uuid.UUID | None] = mapped_column()
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(Text)
    decided_auto_approved: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
