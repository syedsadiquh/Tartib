"""ORM models — importing this package registers every table on ``Base.metadata``.

Alembic's ``env.py`` imports this module so autogenerate sees the whole schema; the
engine and the API import models through here too, never through a single module.
"""

from .agent import AgentProposal, AgentRequestLog, AgentToken
from .auth import AuthSession, MagicLink, PasskeyCredential, UserAccount
from .base import (
    OWNER_ID,
    AttributionMixin,
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UpdatedAtMixin,
    UserScopedMixin,
)
from .calendar import Calendar, ExternalEvent
from .google import GoogleAccount, OAuthState
from .habit import Habit, HabitOccurrence
from .infra import (
    BackupRun,
    CalendarWatch,
    DataVersion,
    Heartbeat,
    IdempotencyKey,
    Job,
    NotificationLog,
    NotionMirrorState,
    PushSubscription,
    ScheduledRun,
    Secret,
    UndoAction,
)
from .log import Activity, AuditEntry, EngineLog
from .placement import Placement
from .plan import CalendarOrphan, DayOverride, PlanRun, SuppressedChange
from .prayer import PrayerInstance
from .settings import AppSetting, VocabItem
from .task import ImportBatch, Subtask, Task, TaskDependency

__all__ = [
    "OWNER_ID",
    "Activity",
    "AgentProposal",
    "AgentRequestLog",
    "AgentToken",
    "AppSetting",
    "AttributionMixin",
    "AuditEntry",
    "AuthSession",
    "BackupRun",
    "Base",
    "Calendar",
    "CalendarOrphan",
    "CalendarWatch",
    "CreatedAtMixin",
    "DataVersion",
    "DayOverride",
    "EngineLog",
    "ExternalEvent",
    "GoogleAccount",
    "Habit",
    "HabitOccurrence",
    "Heartbeat",
    "IdempotencyKey",
    "ImportBatch",
    "Job",
    "MagicLink",
    "NotificationLog",
    "NotionMirrorState",
    "OAuthState",
    "PasskeyCredential",
    "Placement",
    "PlanRun",
    "PrayerInstance",
    "PushSubscription",
    "ScheduledRun",
    "Secret",
    "Subtask",
    "SuppressedChange",
    "Task",
    "TaskDependency",
    "TimestampMixin",
    "UndoAction",
    "UpdatedAtMixin",
    "UserAccount",
    "UserScopedMixin",
    "VocabItem",
]
