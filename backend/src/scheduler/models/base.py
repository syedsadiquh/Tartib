"""Declarative base, shared mixins and column helpers (02-data-model §1).

Conventions this module keeps in one place:

* every table lives in schema ``public`` and shares one ``MetaData`` whose naming
  convention names constraints deterministically, so Alembic renders stable DDL;
* ``id`` columns are ``uuid`` with the PostgreSQL ``uuidv7()`` server default
  (time-ordered, PG 18+) unless the data model says otherwise;
* instants are ``timestamptz`` (``DateTime(timezone=True)``), local days are
  ``date``, times-of-day are ``time``, durations are integer ``*_min``;
* enum-like columns are ``text`` + ``CHECK (...)`` — never native PG enums, so a
  new value is an ordinary migration instead of a type rewrite.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Text

# Postgres's own names are unpredictable for unnamed objects; fix them once here.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every ORM module."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    """``id uuid PRIMARY KEY DEFAULT uuidv7()`` — call once per table."""
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))


class CreatedAtMixin:
    """``created_at timestamptz NOT NULL DEFAULT now()``; most tables carry it."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UpdatedAtMixin:
    """``updated_at timestamptz NOT NULL DEFAULT now()`` for mutable tables.

    The ORM refreshes it on update; the server default covers raw SQL inserts.
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TimestampMixin(CreatedAtMixin, UpdatedAtMixin):
    """Tables that carry both ``created_at`` and ``updated_at``."""


# The single-user default. DB-02 seeds ``user_account`` with exactly this id, so a
# fresh install's rows get it from the server default; adding users later is an
# insert plus explicit ``user_id`` values, never a column backfill (D-42).
OWNER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class UserScopedMixin:
    """``user_id`` — the tenant key on every table that belongs to a user (D-42).

    Tartib ships as a single-user app, so the column defaults to the seeded owner
    row instead of being nullable: a fresh install writes rows with no ``user_id``
    in the INSERT and still satisfies the NOT NULL. Adding a second user later is
    an insert plus explicit ids — not a column backfill across forty tables.
    """

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        server_default=text(f"'{OWNER_ID}'::uuid"),
        nullable=False,
    )


class AttributionMixin:
    """AGT-6 attribution columns, on every table the data model marks ``[attr]``.

    ``actor`` is ``'user' | 'agent:<name>' | 'engine' | 'system'``;
    ``*_auto_approved`` records that an agent action ran without a proposal
    because its scope was pre-approved.
    """

    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_auto_approved: Mapped[bool] = mapped_column(
        server_default=text("false"), nullable=False
    )
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_auto_approved: Mapped[bool] = mapped_column(
        server_default=text("false"), nullable=False
    )
