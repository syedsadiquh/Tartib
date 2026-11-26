"""Google account and the OAuth handshake (02-data-model §2.3, IN-02)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, UserScopedMixin


class GoogleAccount(UserScopedMixin, Base):
    """One row per user. Tokens are Fernet ciphertext."""

    __tablename__ = "google_account"
    __table_args__ = (
        UniqueConstraint("user_id"),
        CheckConstraint("status IN ('connected','expired','revoked','error')", name="status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    refresh_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthState(CreatedAtMixin, Base):
    """CSRF state for the OAuth dance; valid for 10 minutes, then ignored."""

    __tablename__ = "oauth_state"

    state: Mapped[str] = mapped_column(Text, primary_key=True)
    code_verifier: Mapped[str] = mapped_column(Text, nullable=False)
