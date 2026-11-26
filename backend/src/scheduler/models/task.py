"""Tasks, subtasks, dependencies and import batches (02-data-model §2.4)."""

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
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import AttributionMixin, Base, CreatedAtMixin, TimestampMixin, uuid_pk

TASK_STATES = ("inbox", "scheduled", "in_progress", "partial", "done", "skipped", "backlog")
TASK_SOURCES = ("manual", "nl", "bulk", "agent", "recurrence")


class Task(TimestampMixin, AttributionMixin, Base):
    """A unit of work. Nullable columns are the capture gates (SET-0/TSK-3)."""

    __tablename__ = "task"
    __table_args__ = (
        CheckConstraint("length(title) BETWEEN 1 AND 300", name="title_length"),
        CheckConstraint("est_min > 0", name="est_min_positive"),
        CheckConstraint("min_chunk_min >= 5", name="min_chunk_floor"),
        CheckConstraint(
            "state IN ('inbox','scheduled','in_progress','partial','done','skipped','backlog')",
            name="state",
        ),
        CheckConstraint("logged_min >= 0", name="logged_min_non_negative"),
        CheckConstraint("source IN ('manual','nl','bulk','agent','recurrence')", name="source"),
        UniqueConstraint("series_id", "series_date"),
        Index(
            "ix_task_state_active",
            "state",
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index(
            "ix_task_deadline_active",
            "deadline",
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index("ix_task_created_by", "created_by"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, server_default=text("''"), nullable=False)
    est_min: Mapped[int | None] = mapped_column(Integer)
    priority_key: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effort_key: Mapped[str | None] = mapped_column(Text)
    split_key: Mapped[str] = mapped_column(Text, nullable=False)
    subject_key: Mapped[str | None] = mapped_column(Text)
    calendar_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("calendar.id"))
    calendar_inferred: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    min_chunk_min: Mapped[int | None] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(Text, server_default=text("'inbox'"), nullable=False)
    logged_min: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    deferred_until: Mapped[date | None] = mapped_column(Date)
    flag_code: Mapped[str | None] = mapped_column(Text)
    flag_reason: Mapped[str | None] = mapped_column(Text)
    flag_short_min: Mapped[int | None] = mapped_column(Integer)
    flag_raised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flag_reminded_on: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(Text, server_default=text("'manual'"), nullable=False)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("import_batch.id"))
    recurrence: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    series_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("task.id"))
    series_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Subtask(Base):
    """A slice of a task; ``sum(weight_min)`` must equal ``task.est_min`` when present."""

    __tablename__ = "subtask"

    id: Mapped[uuid.UUID] = uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    weight_min: Mapped[int] = mapped_column(Integer, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dropped: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)

    __table_args__ = (CheckConstraint("weight_min > 0", name="weight_positive"),)


class TaskDependency(Base):
    """``task`` must be scheduled after ``depends_on_task``; cycles are a service check."""

    __tablename__ = "task_dependency"
    __table_args__ = (CheckConstraint("task_id <> depends_on_task_id", name="no_self_dependency"),)

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), primary_key=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), primary_key=True
    )


class ImportBatch(CreatedAtMixin, Base):
    """CAP-3: a paste/import draft, committed or discarded as a whole."""

    __tablename__ = "import_batch"
    __table_args__ = (
        CheckConstraint("source IN ('nl','bulk','agent')", name="source"),
        CheckConstraint("status IN ('draft','committed','discarded')", name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    source: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    rows: Mapped[Any] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"), nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
