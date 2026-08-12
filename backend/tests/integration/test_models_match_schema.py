"""The models and the migration describe the same nine tables.

They are written twice — the migration is frozen by design — so something has
to check they still agree. Drift here would surface as a query that fails only
in production, which for a local installation means on someone else's machine.
"""

from __future__ import annotations

from sqlalchemy import Engine, inspect

from app.db.base import Base
from app.db.models import __all__ as exported_models

EXPECTED_TABLES = {
    "candidates",
    "setup_state",
    "provider_configurations",
    "candidate_profiles",
    "documents",
    "parse_jobs",
    "profile_entries",
    "profile_versions",
    "llm_call_logs",
}


def test_every_table_of_the_migration_has_a_model() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert len(exported_models) == len(EXPECTED_TABLES)


def test_columns_and_nullability_match_the_migrated_schema(db_engine: Engine) -> None:
    inspector = inspect(db_engine)
    mismatches: list[str] = []

    for name, table in sorted(Base.metadata.tables.items()):
        if not inspector.has_table(name):
            mismatches.append(f"{name}: the model exists, the table does not")
            continue

        in_database = {
            column["name"]: bool(column["nullable"]) for column in inspector.get_columns(name)
        }
        in_model = {column.name: column.nullable for column in table.columns}

        if set(in_model) != set(in_database):
            only_model = sorted(set(in_model) - set(in_database))
            only_database = sorted(set(in_database) - set(in_model))
            mismatches.append(
                f"{name}: only in the model {only_model}, only in the database {only_database}"
            )
            continue

        for column, nullable in in_model.items():
            if nullable != in_database[column]:
                mismatches.append(
                    f"{name}.{column}: model nullable={nullable}, "
                    f"database nullable={in_database[column]}"
                )

    assert not mismatches, "Models and migration disagree:\n" + "\n".join(mismatches)
