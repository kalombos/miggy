import pathlib
from collections.abc import Generator
from typing import Any

import peewee as pw
import playhouse.db_url
import pytest

POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"


@pytest.fixture()
def migrations_dir():
    """Migrations dir"""
    return pathlib.Path(__file__).with_name("migrations")


@pytest.fixture(params=["sqlite", "postgresql"])
def database(request: pytest.FixtureRequest):
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


@pytest.fixture(params=({"in_transaction": True},))
def patched_pg_db(request: pytest.FixtureRequest) -> Generator[PatchedPgDatabase, Any, None]:
    db = PatchedPgDatabase(POSTGRES_DSN)
    if request.param.get("in_transaction"):
        with db.transaction() as transaction:
            yield db
            transaction.rollback()
    else:
        yield db
    db.close()
    db.clear_queries()
