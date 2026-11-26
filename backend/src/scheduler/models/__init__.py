"""ORM models — importing this package registers every table on ``Base.metadata``.

Alembic's ``env.py`` imports this module so autogenerate sees the whole schema; the
engine and the API import models through here too, never through a single module.
"""

from .agent import AgentProposal, AgentRequestLog, AgentToken
from .auth import AuthSession, MagicLink, PasskeyCredential, UserAccount
from .base import (
    AttributionMixin,
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UpdatedAtMixin,
)
from .calendar import Calendar, ExternalEvent
from .google import GoogleAccount, OAuthState
from .habit import Habit, HabitOccurrence
from .prayer import PrayerInstance
from .settings import AppSetting, VocabItem
from .task import ImportBatch, Subtask, Task, TaskDependency

__all__ = [
    "AgentProposal",
    "AgentRequestLog",
    "AgentToken",
    "AppSetting",
    "AttributionMixin",
    "AuthSession",
    "Base",
    "Calendar",
    "CreatedAtMixin",
    "ExternalEvent",
    "GoogleAccount",
    "Habit",
    "HabitOccurrence",
    "ImportBatch",
    "MagicLink",
    "OAuthState",
    "PasskeyCredential",
    "PrayerInstance",
    "Subtask",
    "Task",
    "TaskDependency",
    "TimestampMixin",
    "UpdatedAtMixin",
    "UserAccount",
    "VocabItem",
]
