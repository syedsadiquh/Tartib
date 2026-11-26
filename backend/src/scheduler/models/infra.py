"""Infra tables: queue, runs, watch channels, idempotency, push, secrets (02-data-model §2.9)."""

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
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import OWNER_ID, Base, UserScopedMixin, uuid_pk


class Job(Base):
    """WK-01 queue row; ``dedupe_key`` coalesces bursts while a job is queued."""

    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','done','failed')", name="status"),
        Index(
            "job_dedupe_queued",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status = 'queued' AND dedupe_key IS NOT NULL"),
        ),
        Index("ix_job_status_run_after", "status", "run_after"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("3"), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScheduledRun(Base):
    """NFR-3: one row per scheduled job firing, including missed runs."""

    __tablename__ = "scheduled_run"
    __table_args__ = (
        CheckConstraint("status IN ('started','ok','failed','missed')", name="status"),
        Index("ix_scheduled_run_job", "job_name", text("scheduled_for DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class CalendarWatch(UserScopedMixin, Base):
    """D-29/IN-15: an active Google push channel for one calendar."""

    __tablename__ = "calendar_watch"

    channel_id: Mapped[str] = mapped_column(Text, primary_key=True)
    calendar_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calendar.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DataVersion(Base):
    """D-29 live refresh: exactly one row; the trigger in §2.9 bumps it."""

    __tablename__ = "data_version"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    version: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    bumped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Heartbeat(Base):
    """Worker liveness marker, read by the watchdog."""

    __tablename__ = "heartbeat"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    beat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UndoAction(UserScopedMixin, Base):
    """D-22: a reversible action stored as a service call plus its arguments."""

    __tablename__ = "undo_action"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    inverse: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyKey(Base):
    """NFR-8: replay safety for offline mutations; purged after 48 h."""

    __tablename__ = "idempotency_key"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class PushSubscription(UserScopedMixin, Base):
    """A Web Push endpoint; ``failures`` drives pruning after repeated 410s."""

    __tablename__ = "push_subscription"

    id: Mapped[uuid.UUID] = uuid_pk()
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failures: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)


class NotificationLog(UserScopedMixin, Base):
    """OVL-3: one row per notification, keyed so the same reminder never repeats."""

    __tablename__ = "notification_log"
    __table_args__ = (
        CheckConstraint(
            "type IN ('block_start','prayer','plan_approval','overload','alert','magic_link')",
            name="type",
        ),
        UniqueConstraint("user_id", "dedupe_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class Secret(Base):
    """D-18: a UI-entered secret stored as Fernet ciphertext."""

    __tablename__ = "secret"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        primary_key=True,
        server_default=text(f"'{OWNER_ID}'::uuid"),
    )
    name: Mapped[str] = mapped_column(Text, primary_key=True)
    value_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class NotionMirrorState(UserScopedMixin, Base):
    """Last mirrored page and content hash per entity."""

    __tablename__ = "notion_mirror_state"

    entity_type: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_id: Mapped[str] = mapped_column(Text, primary_key=True)
    notion_page_id: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BackupRun(UserScopedMixin, Base):
    """One backup/mirror/restore attempt and its result."""

    __tablename__ = "backup_run"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('notion_mirror','restore_dry_run','restore_apply','pg_dump')",
            name="kind",
        ),
        CheckConstraint("status IN ('running','ok','failed')", name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
