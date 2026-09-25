import os
import pathlib
from textwrap import dedent
from unittest import mock

import peewee as pw
import playhouse
import pytest
from playhouse.migrate import Operation
from playhouse.postgres_ext import Psycopg3Database

from miggy.operations import AddField, MigrateOperation, RemoveField, RunSql
from miggy.router import Migration, Router, detect_changes, get_router
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


def test_router_schema(tmpdir):
    schema_name = "test"
    migrations = tmpdir.mkdir("migrations")

    with mock.patch("miggy.router.Router.done"):
        router = Router(database="postgres:///fake", migrate_dir=str(migrations), schema=schema_name)

        assert router.schema == schema_name
        # TODO: test schema change


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
        router = Router(
            db,
            migrate_dir=resources_dir / "transaction_test",
        )
        router.run_one(migration_name, change_schema=True, change_history=True)
        transaction_called = mocked.call_count == 1
        assert transaction_called is expected


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
                '''
        def migrate(migrator, database, fake=False):
            """Write your migrations here."""

            migrator.add_field(
                model_name='test',
                name='field',
                field=pw.IntegerField(constraints=[pw.SQL('DEFAULT 5')]),
            )

            migrator.alter_field(
                model_name='test',
                name='first_name',
                field=pw.CharField(default=tests.helpers.get_active_status),
            )


        def rollback(migrator, database, fake=False):
            """Write your rollback migrations here."""
        '''
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


def test_router_add_operation(router: Router) -> None:
    class User(pw.Model):
        name = pw.CharField()

    router.state["user"] = User

    operations = router.add_operation(AddField("user", "email", pw.CharField(max_length=255, null=True)))

    user = router.state["user"]
    assert isinstance(user.email, pw.CharField)
    assert user.email.max_length == 255
    assert user.email.null is True
    assert len(operations) == 1
    assert isinstance(operations[0], Operation)


def test_router_run_operations(router: Router, patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    router.state["user"] = User
    patched_pg_db.clear_queries()

    operations = router.add_operation(RemoveField("user", "last_name"))
    router.run_operations(operations)

    assert not hasattr(router.state["user"], "last_name")
    assert patched_pg_db.queries[-1] == 'ALTER TABLE "user" DROP COLUMN "last_name"'


def test_router_run_operations_selects_schema(patched_pg_db: PatchedPgDatabase, migrations_dir: pathlib.Path) -> None:
    schema_name = "test_schema"
    patched_pg_db.execute_sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
    router = Router(patched_pg_db, migrate_dir=migrations_dir, schema=schema_name)
    patched_pg_db.clear_queries()

    operations = router.add_operation(RunSql("SELECT 1"))
    router.run_operations(operations)

    assert patched_pg_db.queries[0] == f'SET search_path TO "{schema_name}"'
    patched_pg_db.execute_sql(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE;")


def test_router_change_history(router: Router) -> None:
    assert router.done == []

    router.change_history("001_test", downgrade=False)
    assert router.done == ["001_test"]

    router.change_history("001_test", downgrade=True)
    assert router.done == []


def _build_migration(
    migrate: list[MigrateOperation],
    rollback: list[MigrateOperation],
    atomic: bool = True,
) -> Migration:
    class _Migration(Migration):
        pass

    _Migration.atomic = atomic
    _Migration.migrate = migrate
    _Migration.rollback = rollback
    return _Migration()


def test_router_add_operations_not_downgrade(router: Router, patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField(null=True)

        class Meta:
            database = patched_pg_db

    User.create_table()
    router.state["user"] = User

    migration = _build_migration(
        migrate=[RemoveField("user", "email")],
        rollback=[],
    )

    operations = router.add_operations(migration, downgrade=False)
    assert len(operations) == 1

    router.run_operations(operations)
    assert not hasattr(router.state["user"], "email")


def test_router_add_operations_downgrade(router: Router, patched_pg_db: PatchedPgDatabase) -> None:
    class Order(pw.Model):
        number = pw.CharField()

        class Meta:
            database = patched_pg_db

    Order.create_table()
    router.state["order"] = Order

    migration = _build_migration(
        migrate=[],
        rollback=[AddField("order", "phone", pw.CharField(null=True))],
    )

    operations = router.add_operations(migration, downgrade=True)
    assert len(operations) == 1

    router.run_operations(operations)
    assert isinstance(router.state["order"].phone, pw.CharField)


def test_router_run_one__only_state(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.create_model("tag", fields={"tag": pw.CharField()})
            """
        )
    )
    router = Router(db, migrate_dir=mig_dir)

    router.run_one("001_create", change_schema=False, change_history=False)

    assert "tag" in router.state
    assert not db.table_exists("tag")


def test_router_run_one(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.create_model("tag", fields={"tag": pw.CharField()})


            def rollback(migrator, database, fake=False):
                migrator.remove_model("tag")
            """
        )
    )
    name = "001_create"
    router = Router(db, migrate_dir=mig_dir)

    router.run_one(name, change_schema=True, change_history=True)

    assert "tag" in router.state
    assert db.table_exists("tag")

    router.run_one(name, change_schema=True, change_history=True, downgrade=True)
    assert "tag" not in router.state
    assert not db.table_exists("tag")


def test_router_build_state_from_migrations(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.create_model("tag", fields={"tag": pw.CharField()})
            """
        )
    )
    router = Router(db, migrate_dir=mig_dir)
    router.model.create(name="001_create")

    router.build_state_from_migrations()

    assert "tag" in router.state
