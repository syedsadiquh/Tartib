"""Database fixtures for the service tests.

The schema is built by running the real Alembic migration against
``TEST_DATABASE_URL`` once per session — the tests therefore prove the migration,
not just the ORM metadata. Every test starts from empty tables and leaves none
behind, so order never matters.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from scheduler.config import get_env
from scheduler.models import OWNER_ID, Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Fresh migrated test database for the whole session."""
    url = get_env().TEST_DATABASE_URL
    engine = create_engine(url)
    with engine.begin() as conn:
        # A leftover schema from an earlier run would make `upgrade head` fail.
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Session bound to the migrated test database; tables are emptied afterwards.

    The owner row is seeded first: every ``user_id`` column defaults to it (D-42),
    so without the row the foreign key would reject the insert.
    """
    session = Session(db_engine)
    session.execute(
        text(
            "INSERT INTO user_account (id, email) "
            "VALUES (:id, 'owner@example.test') ON CONFLICT DO NOTHING"
        ),
        {"id": OWNER_ID},
    )
    session.commit()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

    tables = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))
    with db_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
