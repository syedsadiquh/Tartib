"""Calendars and inbound busy events (02-data-model §2.3, SET-2 / IN-05)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UpdatedAtMixin, uuid_pk


class Calendar(TimestampMixin, Base):
    """A discovered Google calendar plus the per-calendar routing rules."""

    __tablename__ = "calendar"
    __table_args__ = (
        CheckConstraint("NOT writable OR access_role IN ('owner','writer')", name="writable_role"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    google_calendar_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(Text, nullable=False)
    access_role: Mapped[str] = mapped_column(Text, nullable=False)
    read_meetings: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    writable: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    treat_as_busy: Mapped[bool] = mapped_column(
        Boolean, server_default=text("true"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    sync_token: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExternalEvent(UpdatedAtMixin, Base):
    """A meeting or other busy event; an obstacle per OFF-2, never app-owned.

    Events the app wrote are detected by their extended property (IN-05) and are
    never stored here — they live in ``placement``.
    """

    __tablename__ = "external_event"
    __table_args__ = (
        UniqueConstraint("calendar_id", "google_event_id"),
        Index("ix_external_event_start_end", "start_at", "end_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calendar.id", ondelete="CASCADE"), nullable=False
    )
    google_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, server_default=text("''"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    transparency: Mapped[str] = mapped_column(Text, server_default=text("'opaque'"), nullable=False)
    response_status: Mapped[str | None] = mapped_column(Text)
    cancelled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    etag: Mapped[str | None] = mapped_column(Text)
