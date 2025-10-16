import pathlib
from collections.abc import Generator
from typing import Any

import peewee as pw
import playhouse.db_url
import pytest
from playhouse.db_url import connect

from peewee_migrate.migrator import Migrator

POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"


@pytest.fixture()
def migrations_dir():
    """Migrations dir"""
    return pathlib.Path(__file__).with_name("migrations")


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request):
    if request.param == "sqlite":
        db = playhouse.db_url.connect("sqlite:///:memory:")
    else:
        db = playhouse.db_url.connect(POSTGRES_DSN)

    with db.atomic():
        yield db
        db.rollback()


@pytest.fixture()
def router(migrations_dir, database):
    from peewee_migrate.cli import get_router

    router = get_router(migrations_dir, database)

    assert router.database is database
    assert isinstance(router.database, pw.Database)

    return router


class PatchedPgDatabase(pw.PostgresqlDatabase):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.queries: list[str] = []

    def clear_queries(self) -> None:
        self.queries = []

    def execute_sql(self, sql, params=None, commit=None) -> Any:
        _sql = sql if params is None else sql % tuple(params)
        self.queries.append(_sql)
        return super().execute_sql(sql, params, commit)


@pytest.fixture()
def patched_pg_db() -> Generator[PatchedPgDatabase, Any, None]:
    db = PatchedPgDatabase(POSTGRES_DSN)
    with db.transaction() as transaction:
        yield db
        transaction.rollback()
    db.close()
    db.clear_queries()


@pytest.fixture
def sq_migrator() -> Migrator:
    return Migrator(connect("sqlite:///:memory:"))
