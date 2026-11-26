"""Single owner account, passkeys, sessions and magic links (02-data-model §2.2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, LargeBinary, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, INET
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, uuid_pk


class UserAccount(CreatedAtMixin, Base):
    """Exactly one row: the owner. Seeded from ``OWNER_EMAIL`` by DB-02."""

    __tablename__ = "user_account"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, server_default=text("'Me'"), nullable=False)


class PasskeyCredential(CreatedAtMixin, Base):
    """A WebAuthn credential. ``credential_id``/``public_key`` are raw bytes."""

    __tablename__ = "passkey_credential"

    id: Mapped[uuid.UUID] = uuid_pk()
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"), nullable=False)
    transports: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(CreatedAtMixin, Base):
    """Sliding 30-day session; only the HMAC of the cookie token is stored."""

    __tablename__ = "auth_session"

    id: Mapped[uuid.UUID] = uuid_pk()
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MagicLink(CreatedAtMixin, Base):
    """Passwordless login link; valid for 15 minutes and single use."""

    __tablename__ = "magic_link"

    token_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
