"""ORM models — importing this package registers every table on ``Base.metadata``.

Alembic's ``env.py`` imports this module so autogenerate sees the whole schema; the
engine and the API import models through here too, never through a single module.
"""

from .base import (
    AttributionMixin,
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UpdatedAtMixin,
)
from .settings import AppSetting, VocabItem

__all__ = [
    "AppSetting",
    "AttributionMixin",
    "Base",
    "CreatedAtMixin",
    "TimestampMixin",
    "UpdatedAtMixin",
    "VocabItem",
]
