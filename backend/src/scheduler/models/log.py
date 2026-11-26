"""Engine log, activity history and audit trail (02-data-model §2.8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UserScopedMixin


class EngineLog(UserScopedMixin, Base):
    """RPL-6/G4: one row per engine decision, shown in the Log screen."""

    __tablename__ = "engine_log"
    __table_args__ = (
        CheckConstraint(
            "category IN ('shrink','held','prayer','release','placement','flag',"
            "'pin','sync','apply','system')",
            name="category",
        ),
        Index("ix_engine_log_ts", text("ts DESC")),
        Index("ix_engine_log_subject", "subject_type", "subject_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    plan_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plan_run.id"))
    rule: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str | None] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID | None] = mapped_column()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, server_default=text("''"), nullable=False)
    effect: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    auto_approved: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    undo_token: Mapped[str | None] = mapped_column(Text)


class Activity(UserScopedMixin, Base):
    """Per-entity history shown on the task detail screen (AGT-7)."""

    __tablename__ = "activity"
    __table_args__ = (Index("ix_activity_entity", "entity_type", "entity_id", text("ts DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    auto_approved: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )


class AuditEntry(UserScopedMixin, Base):
    """SET-14: settings and security changes with before/after snapshots."""

    __tablename__ = "audit_entry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    area: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
