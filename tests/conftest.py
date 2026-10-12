import pathlib
from collections.abc import Generator
from typing import Any

import peewee as pw
import pytest

from miggy.router import Router

POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"


@pytest.fixture()
def resources_dir() -> pathlib.Path:
    return pathlib.Path(__file__).with_name("resources")


class PatchedPgDatabase(pw.PostgresqlDatabase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.queries: list[str] = []

    def clean(self):
        self.execute_sql("DROP SCHEMA IF EXISTS public CASCADE;")
        self.execute_sql("CREATE SCHEMA public;")
        self.clear_queries()

    def clear_queries(self) -> None:
        self.queries = []

    def execute_sql(self, sql, params=None) -> Any:
        _sql = sql if params is None else sql % tuple(params)
        self.queries.append(_sql)
        return super().execute_sql(sql, params)


@pytest.fixture(params=({"in_transaction": True},))
def patched_pg_db(request: pytest.FixtureRequest) -> Generator[PatchedPgDatabase, Any, None]:
    db = PatchedPgDatabase(POSTGRES_DSN)
    try:
        yield db
    finally:
        db.clean()
        db.close()


@pytest.fixture()
def migrations_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "migrations"
    d.mkdir()
    return tmp_path


@pytest.fixture()
def router(migrations_dir: pathlib.Path, patched_pg_db: PatchedPgDatabase) -> Router:
    return Router(patched_pg_db, migrate_dir=migrations_dir)


@pytest.fixture()
def person_migrations_dir(resources_dir: pathlib.Path) -> pathlib.Path:
    return resources_dir / "person_migrations"


@pytest.fixture()
def person_router(person_migrations_dir: pathlib.Path, patched_pg_db: PatchedPgDatabase) -> Router:
    return Router(patched_pg_db, migrate_dir=person_migrations_dir)
