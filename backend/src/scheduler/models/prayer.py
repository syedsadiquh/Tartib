"""Daily prayer instances (02-data-model §2.6)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UpdatedAtMixin, UserScopedMixin, uuid_pk

PRAYER_NAMES = ("fajr", "dhuhr", "asr", "maghrib", "isha")


class PrayerInstance(UserScopedMixin, UpdatedAtMixin, Base):
    """One row per prayer per local day; the block lives in ``placement``."""

    __tablename__ = "prayer_instance"
    __table_args__ = (
        UniqueConstraint("date", "name"),
        CheckConstraint("name IN ('fajr','dhuhr','jummah','asr','maghrib','isha')", name="name"),
        CheckConstraint("state IN ('normal','shifted','qada','prayed')", name="state"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    drift_min: Mapped[int | None] = mapped_column(Integer)
    drift_flag: Mapped[bool] = mapped_column(server_default=text("false"), nullable=False)
    state: Mapped[str] = mapped_column(Text, server_default=text("'normal'"), nullable=False)
    qada_index: Mapped[int | None] = mapped_column(Integer)
    prayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prayed_by: Mapped[str | None] = mapped_column(Text)
