import os
import pathlib
from textwrap import dedent
from unittest import mock

import peewee as pw
import pytest

try:
    from playhouse.postgres_ext import Psycopg3Database
except ImportError:  # peewee == 3.17.9
    Psycopg3Database = None

from miggy.router import FakeInitialError, MigrationError, Router, detect_changes, get_router
from miggy.state import State
from tests.conftest import POSTGRES_DSN, PatchedPgDatabase
from tests.helpers import get_active_status


def test_router_run_already_applied_ok(router: Router) -> None:
    router.run()
    router.build_state_from_migrations()
    Person = router.state["person"]

    assert Person.get_or_none(email="person@example.com") is not None

    Person.delete().execute()

    router.run_one("004_test_insert")
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
    ("schema", "expected"),
    [
        ("test_schema", ["SET search_path TO test_schema"]),
        (None, []),
    ],
)
def test_router_resolve_schema(
    schema: str | None, expected: list[str], patched_pg_db: PatchedPgDatabase, migrations_dir: pathlib.Path
) -> None:
    patched_pg_db.execute_sql("CREATE SCHEMA IF NOT EXISTS test_schema;")
    router = Router(patched_pg_db, migrate_dir=migrations_dir, schema=schema)
    patched_pg_db.clear_queries()

    router.resolve_schema()

    assert patched_pg_db.queries == expected
    patched_pg_db.execute_sql("DROP SCHEMA IF EXISTS test_schema CASCADE;")


@pytest.mark.skipif(Psycopg3Database is None, reason="Psycopg3Database requires peewee >= 3.18")
def test_compile(tmp_path: pathlib.Path) -> None:
    def from_state() -> State:
        class Test(pw.Model):
            first_name = pw.CharField()

            class Meta:
                table_name = "test"

        return State({"test": Test})

    def _to_state() -> State:
        class Test(pw.Model):
            first_name = pw.CharField(default=get_active_status)
            field = pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])

            class Meta:
                table_name = "test"

        return State({"test": Test})

    changes = detect_changes(from_state(), _to_state())

    d = tmp_path / "migrations"
    d.mkdir()
    router = Router(Psycopg3Database(POSTGRES_DSN), migrate_dir=d)
    router.compile("test_router_compile", changes, [])

    with open(d / "001_test_router_compile.py") as f:
        content = f.read()
        assert (
            dedent(
                """
        class Migration(operations.Migration):
            atomic = True

            forward = [
                operations.AddField(
                    model_name='test',
                    name='field',
                    field=pw.IntegerField(constraints=[pw.SQL('DEFAULT 5')]),
                ),
                operations.AlterField(
                    model_name='test',
                    name='first_name',
                    field=pw.CharField(default=tests.helpers.get_active_status),
                ),
            ]
        """
            )
            in content
        )


def test_get_router_reads_config(tmp_path: pathlib.Path) -> None:
    db_path = tmp_path / "db.sqlite3"
    db_path.touch()
    conf = tmp_path / "miggyconf.py"
    conf.write_text(
        "DATABASE = 'sqlite:///%s'\n"
        "IGNORE = ['ignored_model']\n"
        "SCHEMA = 'config_schema'\n"
        "MIGRATE_TABLE = 'custom_history'\n"
        "MIGRATE_DIR = 'custom_migrations'"
    )

    router = get_router("cli_dir", "sqlite:///:memory:", "cli_schema", 0, conf_path=conf)

    assert router.ignore == ["ignored_model"]
    assert router.schema == "config_schema"
    assert router.migrate_table == "custom_history"
    assert router.migrate_dir == tmp_path / "custom_migrations"
    assert router.working_dir == tmp_path


def test_get_router_defaults_without_conf_path() -> None:
    directory = "migrations"

    with pytest.warns(DeprecationWarning, match="conf_path=None"):
        router = get_router(directory, "sqlite:///:memory:")

    assert isinstance(router, Router)
    assert router.ignore == []
    assert router.schema is None
    assert router.migrate_table == "migratehistory"
    assert router.migrate_dir == pathlib.Path(os.getcwd()) / directory
    assert router.working_dir == pathlib.Path(os.getcwd())


def test_get_router_falls_back_to_legacy_conf_py(tmp_path: pathlib.Path) -> None:
    directory = tmp_path / "some_dir"
    directory.mkdir()
    (directory / "conf.py").write_text("MIGRATE_TABLE = 'legacy_history'\n")

    with pytest.warns(DeprecationWarning, match="conf_path=None"):
        router = get_router(directory, "sqlite:///:memory:")

    assert router.migrate_table == "legacy_history"
    assert router.migrate_dir == pathlib.Path(os.getcwd()) / directory
    assert router.working_dir == pathlib.Path(os.getcwd())


def test_get_router_sys_exit() -> None:
    with pytest.warns(DeprecationWarning, match="conf_path=None"):
        with pytest.raises(SystemExit) as exc_info:
            get_router(str("migrations"), "unknown://foo")

    assert exc_info.value.code == 1


def test_router_unwraps_proxy_database(patched_pg_db: PatchedPgDatabase, migrations_dir: pathlib.Path) -> None:
    proxy = pw.Proxy()
    proxy.initialize(patched_pg_db)

    router = Router(proxy, migrate_dir=migrations_dir)

    assert router.database is patched_pg_db
    assert router.schema_migrator.database is patched_pg_db


def test_router_run_one(tmp_path: pathlib.Path, patched_pg_db: PatchedPgDatabase) -> None:
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw
            from miggy import operations


            class Migration(operations.Migration):
                atomic = True

                forward = [
                    operations.CreateModel(
                        'tag',
                        {'tag': pw.CharField()},
                        {},
                    ),
                ]

                backward = [
                    operations.RemoveModel(
                        'tag',
                    ),
                ]
            """
        )
    )
    name = "001_create"
    router = Router(patched_pg_db, migrate_dir=mig_dir)

    router.run_one(name, change_schema=True, change_history=True)

    assert "tag" in router.state
    assert patched_pg_db.table_exists("tag")

    router.run_one(name, change_schema=True, change_history=True, backward=True)
    assert "tag" not in router.state
    assert not patched_pg_db.table_exists("tag")


def test_router_run_one_resolves_schema(patched_pg_db: PatchedPgDatabase, tmp_path: pathlib.Path) -> None:
    schema_name = "test_schema"
    patched_pg_db.execute_sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw
            from miggy import operations


            class Migration(operations.Migration):
                atomic = True

                forward = [
                    operations.CreateModel(
                        'tag',
                        {'tag': pw.CharField()},
                        {},
                    ),
                ]

                backward = [
                    operations.RemoveModel(
                        'tag',
                    ),
                ]
            """
        )
    )
    router = Router(patched_pg_db, migrate_dir=mig_dir, schema=schema_name)
    patched_pg_db.clear_queries()

    router.run_one("001_create", change_schema=True, change_history=True)

    assert patched_pg_db.queries[1] == f"SET search_path TO {schema_name}"

    patched_pg_db.execute_sql(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE;")


def test_router_read_new_format_wo_transaction(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            from miggy import operations


            class Migration(operations.Migration):
                atomic = False

                forward = [
                    operations.RemoveModel(
                        'tag',
                    ),
                ]
            """
        )
    )
    router = Router(db, migrate_dir=mig_dir)

    migration = router.read("001_create", fake=True)
    assert migration.atomic is False
    assert [type(op).__name__ for op in migration.forward] == ["RemoveModel"]
    assert [type(op).__name__ for op in migration.backward] == []


def test_router_build_state_from_migrations(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw
            from miggy import operations


            class Migration(operations.Migration):
                atomic = True

                forward = [
                    operations.CreateModel(
                        'tag',
                        {'tag': pw.CharField()},
                        {},
                    ),
                ]

                backward = [
                    operations.RemoveModel(
                        'tag',
                    ),
                ]
            """
        )
    )
    router = Router(db, migrate_dir=mig_dir)
    router.model.create(name="001_create")

    router.build_state_from_migrations()

    assert "tag" in router.state


def test_migration_error_hierarchy() -> None:
    assert issubclass(MigrationError, Exception)
    assert issubclass(FakeInitialError, MigrationError)


def test_compile_numbering(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=d)

    assert router.compile("first", [], []) == "001_first"
    assert (d / "001_first.py").exists()

    assert router.compile("second", [], []) == "002_second"
    assert (d / "002_second.py").exists()


def test_compile_attrs_default(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=d)

    name = router.compile("first", [], [])

    content = (d / f"{name}.py").read_text()
    assert "atomic = True" in content
    assert "fake_initial" not in content


def test_compile_fake_initial(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=d)

    name = router.compile("initial", [], [], fake_initial=True)

    assert name == "001_initial"
    content = (d / "001_initial.py").read_text()
    assert "    atomic = True\n\n    fake_initial = True" in content

    migration = router.read(name, fake=True)
    assert migration.atomic is True
    assert migration.fake_initial is True
    assert migration.is_fake_initial() is True


def test_compile_fake_initial_not_first(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=d)
    router.compile("first", [], [])

    with pytest.raises(FakeInitialError, match='only supported for migration "001"'):
        router.compile("second", [], [], fake_initial=True)

    assert not (d / "002_second.py").exists()


def test_compile_fake_initial_explicit_num(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=d)

    with pytest.raises(FakeInitialError, match='got "002_second"'):
        router.compile("second", [], [], num=2, fake_initial=True)

    name = router.compile("initial", [], [], num=1, fake_initial=True)
    assert name == "001_initial"


def test_create_fake_initial(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=d)

    name = router.create("init", fake_initial=True)

    assert name == "001_init"
    assert "fake_initial = True" in (d / "001_init.py").read_text()

    with pytest.raises(FakeInitialError):
        router.create("second", fake_initial=True)


def test_rollback_raises_migration_error(tmp_path: pathlib.Path) -> None:
    d = tmp_path / "migrations"
    d.mkdir()
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=d)

    with pytest.raises(MigrationError, match="No migrations are found."):
        router.rollback("001_test")

    router.model.create(name="001_test")
    router.model.create(name="002_test")

    with pytest.raises(MigrationError, match="Only last migration can be canceled."):
        router.rollback("001_test")
