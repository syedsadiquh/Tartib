"""The mapping registers the right tables and columns (DB-01, slice by slice).

These are metadata-only assertions: they run without a database, so they stay green
while the migration does not exist yet. The Postgres-level guarantees (CHECKs, the
exclusion constraint, partial indexes) are proved in ``tests/services/test_schema.py``
against the real migration.
"""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from scheduler.models import Base


def _default_text(column: object) -> str:
    """The SQL text of a column's server default, or ``""`` when it has none."""
    default = getattr(column, "server_default", None)
    arg = getattr(default, "arg", None)
    return str(getattr(arg, "text", arg))


def test_metadata_uses_the_shared_naming_convention() -> None:
    convention = Base.metadata.naming_convention
    assert convention.get("pk") == "pk_%(table_name)s"
    assert convention.get("ck") == "ck_%(table_name)s_%(constraint_name)s"
    assert convention.get("fk") == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    assert convention.get("ix") == "ix_%(table_name)s_%(column_0_N_name)s"
    assert convention.get("uq") == "uq_%(table_name)s_%(column_0_N_name)s"


def test_settings_tables_are_registered() -> None:
    assert {"app_setting", "vocab_item"} <= set(Base.metadata.tables)


def test_app_setting_is_versioned_and_has_no_created_at() -> None:
    table = Base.metadata.tables["app_setting"]
    assert [c.name for c in table.primary_key.columns] == ["section"]
    assert isinstance(table.c.data.type, JSONB)
    assert _default_text(table.c.version) == "1"
    assert "created_at" not in table.c
    assert "updated_at" in table.c


def test_vocab_item_has_uuid_pk_and_both_timestamps() -> None:
    table = Base.metadata.tables["vocab_item"]
    assert table.c.id.type.python_type is uuid.UUID
    assert _default_text(table.c.id) == "uuidv7()"
    assert isinstance(table.c.created_at.type, DateTime)
    assert isinstance(table.c.updated_at.type, DateTime)
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True
    assert isinstance(table.c.sort.type, Integer)
    assert isinstance(table.c.label.type, Text)


def test_vocab_item_unique_kind_key() -> None:
    table = Base.metadata.tables["vocab_item"]
    unique = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert len(unique) == 1
    assert {c.name for c in unique[0].columns} == {"kind", "key"}
