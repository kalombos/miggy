import pathlib

import peewee as pw
import playhouse.db_url
import pytest

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
