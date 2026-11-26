"""Placements: the calendar blocks the app owns (02-data-model §2.7).

The no-overlap guarantee (FR-7.1) is a Postgres exclusion constraint on the
``tstzrange`` of active, unpinned rows. SQLAlchemy cannot express it portably, so
migration 0001 adds it by hand — see ``backend/migrations/versions/0001_*.py``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import AttributionMixin, Base, TimestampMixin, uuid_pk


class Placement(TimestampMixin, AttributionMixin, Base):
    """A task chunk, habit occurrence, prayer or qada block on a calendar."""

    __tablename__ = "placement"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="end_after_start"),
        CheckConstraint("owner = 'engine' OR pinned", name="user_blocks_pinned"),
        CheckConstraint("ref_type IN ('task','habit','prayer')", name="ref_type"),
        CheckConstraint("kind IN ('task_chunk','habit','prayer','qada')", name="kind"),
        CheckConstraint("owner IN ('engine','user')", name="owner"),
        CheckConstraint("status IN ('active','removed')", name="status"),
        Index(
            "ix_placement_ref_active",
            "ref_type",
            "ref_id",
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_placement_local_date_active",
            "local_date",
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "placement_google_event_id",
            "google_event_id",
            unique=True,
            postgresql_where=text("google_event_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    ref_type: Mapped[str] = mapped_column(Text, nullable=False)
    ref_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calendar_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calendar.id"), nullable=False)
    google_event_id: Mapped[str | None] = mapped_column(Text)
    gcal_etag: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(Text, server_default=text("'engine'"), nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"), nullable=False)
    created_plan_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plan_run.id"))
    updated_plan_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plan_run.id"))
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
