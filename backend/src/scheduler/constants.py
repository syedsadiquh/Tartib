"""Technical (non-scheduling) time constants (SET-0).

Scheduling minutes, windows and thresholds live in the ``app_setting`` table and are
read through ``services/settings.py`` — never here. Only protocol/transport timeouts
belong in this module, and ``scripts/check_no_magic_numbers.py`` treats them as the
single allowed source of named integers.
"""

from __future__ import annotations

#: Undo window after a destructive user action (BE-06).
UNDO_WINDOW_SEC = 15

#: Magic-link lifetime (BE-03).
MAGIC_LINK_TTL_MIN = 15

#: OAuth ``state`` parameter lifetime (IN-02).
OAUTH_STATE_TTL_MIN = 10

#: Refresh Google tokens this long before they expire (IN-02).
TOKEN_REFRESH_LEAD_MIN = 5

#: Queue retry backoff, in seconds, per attempt.
RETRY_BACKOFF_SEC = (5, 30, 120)

#: How often the worker polls the ``job`` table (06-worker-and-jobs, D-29).
JOB_POLL_INTERVAL_SEC = 1

#: Outbound calendar write attempts before the change is rolled back (IN-06).
CALENDAR_WRITE_ATTEMPTS = 2
