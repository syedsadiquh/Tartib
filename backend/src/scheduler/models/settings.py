"""Settings and vocabularies (02-data-model §2.1)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UpdatedAtMixin, uuid_pk


class AppSetting(UpdatedAtMixin, Base):
    """One row per settings section; ``data`` is validated by its Pydantic model.

    ``version`` is the optimistic-concurrency counter and bumps on every write.
    This table has no ``created_at``: the row appears with the seeder (DB-02).
    """

    __tablename__ = "app_setting"

    section: Mapped[str] = mapped_column(Text, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)


class VocabItem(TimestampMixin, Base):
    """SET-17: user-renamable vocabulary. ``key`` never changes after create."""

    __tablename__ = "vocab_item"
    __table_args__ = (
        CheckConstraint("kind IN ('subject','priority','effort','split_mode')", name="kind"),
        UniqueConstraint("kind", "key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sort: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(server_default=text("true"), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), nullable=False
    )
