"""upgrade head -> downgrade base -> upgrade head, against a real Postgres.

Reversibility is part of the Definition of Done of the constitution, and a
downgrade that is written but never run is a downgrade that does not work. This
test runs it and compares the schema before and after, so anything the
downgrade forgets to drop — a type, a function, an extension — shows up as a
difference instead of as a broken upgrade months later (ADR-009).
"""

from __future__ import annotations

from typing import Any

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.core.config import LOCAL_CANDIDATE_ID, get_settings
from tests.conftest import alembic_config

SCHEMA_QUERIES: dict[str, str] = {
    "tables": "select tablename from pg_tables where schemaname = 'public' order by 1",
    "enums": """
        select t.typname || ':' || string_agg(e.enumlabel, ',' order by e.enumsortorder)
        from pg_type t
        join pg_enum e on e.enumtypid = t.oid
        group by t.typname
        order by 1
    """,
    "constraints": """
        select conname from pg_constraint
        where connamespace = 'public'::regnamespace
        order by 1
    """,
    "indexes": "select indexname from pg_indexes where schemaname = 'public' order by 1",
    "triggers": "select tgname from pg_trigger where not tgisinternal order by 1",
    "functions": """
        select proname from pg_proc
        where pronamespace = 'public'::regnamespace
        order by 1
    """,
    "extensions": "select extname from pg_extension order by 1",
}


def schema_fingerprint(engine: Engine) -> dict[str, list[Any]]:
    with engine.connect() as connection:
        return {
            name: [row[0] for row in connection.execute(text(query))]
            for name, query in SCHEMA_QUERIES.items()
        }


@pytest.fixture
def engine(migrated_database: str) -> Engine:
    return create_engine(migrated_database, future=True)


def test_downgrade_and_upgrade_restore_the_same_schema(
    migrated_database: str, engine: Engine
) -> None:
    config = alembic_config(migrated_database)
    before = schema_fingerprint(engine)

    command.downgrade(config, "base")
    emptied = schema_fingerprint(engine)

    # Only Alembic's own bookkeeping survives base.
    assert emptied["tables"] == ["alembic_version"]
    assert emptied["enums"] == []
    assert emptied["triggers"] == []
    assert "forbid_profile_version_mutation" not in emptied["functions"]
    assert "vector" not in emptied["extensions"]

    command.upgrade(config, "head")
    after = schema_fingerprint(engine)

    assert after == before


def test_head_carries_the_twelve_enums_and_nine_tables(engine: Engine) -> None:
    fingerprint = schema_fingerprint(engine)

    assert len(fingerprint["enums"]) == 12
    # Nine tables plus alembic_version.
    assert len(fingerprint["tables"]) == 10
    assert "vector" in fingerprint["extensions"]
    assert fingerprint["triggers"] == ["trg_profile_versions_immutable"]


def test_the_seeded_candidate_matches_the_configured_one(db_session: Session) -> None:
    """The literal in the migration and the constant in Settings must agree.

    They are written twice on purpose — a migration must not change what it
    inserted because a constant moved — so something has to check they still
    say the same thing (research R-11).
    """
    seeded = db_session.execute(text("select id from candidates")).scalars().all()

    assert seeded == [LOCAL_CANDIDATE_ID]
    assert get_settings().candidate_id == LOCAL_CANDIDATE_ID
