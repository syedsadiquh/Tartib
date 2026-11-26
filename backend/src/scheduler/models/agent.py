"""Agent tokens, request accounting and held proposals (02-data-model §2.2, AGT-2..10)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, uuid_pk


class AgentToken(CreatedAtMixin, Base):
    """``actor`` for this token is ``'agent:' || name``; only the hash is stored."""

    __tablename__ = "agent_token"
    __table_args__ = (
        CheckConstraint("status IN ('active','revoked')", name="status"),
        CheckConstraint("auto_approve <@ scopes", name="auto_approve_subset"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    token_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    auto_approve: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), nullable=False
    )
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_cap: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_max: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRequestLog(Base):
    """Rate-limit window and activity feed; ``rows`` is the batch size."""

    __tablename__ = "agent_request_log"
    __table_args__ = (Index("ix_agent_request_log_token_ts", "token_id", "ts"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_token.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[int] = mapped_column(Integer, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)


class AgentProposal(CreatedAtMixin, Base):
    """AGT-4: an agent action held for the owner's approval, replayable as-is."""

    __tablename__ = "agent_proposal"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('task_create','task_edit','block_move','plan_apply','bulk_create')",
            name="kind",
        ),
        CheckConstraint("status IN ('pending','approved','rejected','expired')", name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    token_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_token.id"), nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
