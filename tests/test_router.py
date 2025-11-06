import os
import pathlib
from unittest import mock

import peewee as pw
import playhouse
import pytest
from playhouse.psycopg3_ext import Psycopg3Database

from miggy.cli import get_router
from miggy.router import Router
from tests.conftest import POSTGRES_DSN


def test_router_run_already_applied_ok(router: Router) -> None:
    router.run()
    Person = router.migrator.state["person"]

    assert Person.get_or_none(email="person@example.com") is not None

    Person.delete().execute()

    router.run_one("004_test_insert", router.migrator)
    assert Person.get_or_none(email="person@example.com") is None


def test_router_todo_diff_done(router: Router, migrations_dir: pathlib.Path):
    MigrateHistory = router.model

    assert router.todo == ["001_test", "002_test", "003_tespy", "004_test_insert"]
    assert router.done == []
    assert router.diff == ["001_test", "002_test", "003_tespy", "004_test_insert"]

    router.create("new")
    assert router.todo == ["001_test", "002_test", "003_tespy", "004_test_insert", "005_new"]
    os.remove(os.path.join(migrations_dir, "005_new.py"))

    MigrateHistory.create(name="001_test")
    assert router.diff == ["002_test", "003_tespy", "004_test_insert"]
    MigrateHistory.delete().execute()


def test_router_rollback(router: Router):
    MigrateHistory = router.model
    router.run()

    migrations = MigrateHistory.select()
    assert list(migrations)
    assert migrations.count() == 4

    router.rollback("004_test_insert")
    router.rollback("003_tespy")
    assert router.diff == ["003_tespy", "004_test_insert"]
    assert migrations.count() == 2


def test_router_merge(router: Router, migrations_dir: pathlib.Path):
    MigrateHistory = router.model
    router.run()

    with mock.patch("os.remove") as mocked:
        router.merge()
        assert mocked.call_count == 4
        assert mocked.call_args[0][0] == os.path.join(migrations_dir, "004_test_insert.py")
        assert MigrateHistory.select().count() == 1

    # after merge we have new migration, remove it for cleanup purposes
    os.remove(os.path.join(migrations_dir, "001_initial.py"))


@pytest.mark.parametrize(
    ("db", "expected"),
    [
        (pw.PostgresqlDatabase(POSTGRES_DSN), "import playhouse.postgres_ext as pw_pext"),
        (Psycopg3Database(POSTGRES_DSN), "import playhouse.psycopg3_ext as pw_pext"),
    ],
)
def test_router_compile(tmp_path: pathlib.Path, db: pw.Database, expected: str) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    router = get_router(d, db)
    router.compile("test_router_compile")

    with open(d / "001_test_router_compile.py") as f:
        content = f.read()
        assert expected in content
        assert "SQL = pw.SQL" in content


def test_router_schema(tmpdir):
    schema_name = "test"
    migrations = tmpdir.mkdir("migrations")

    with mock.patch("miggy.router.BaseRouter.done"):
        router = get_router(str(migrations), "postgres:///fake", schema=schema_name)

        assert router.schema == schema_name
        assert router.migrator.schema == schema_name


@pytest.mark.parametrize(
    ("migration_name", "expected"),
    [
        ("w_transaction", True),
        ("wo_transaction", False),
    ],
)
def test_migration_atomic(resources_dir: pathlib.Path, expected: bool, migration_name: str) -> None:
    db = playhouse.db_url.connect("sqlite:///:memory:")
    with mock.patch.object(db, "transaction") as mocked:
        router = get_router(resources_dir / "transaction_test", db)
        router.run_one(migration_name, router.migrator, change_schema=True, change_history=True)
        transaction_called = mocked.call_count == 1
        assert transaction_called is expected
