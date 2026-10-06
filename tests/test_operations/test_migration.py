import peewee as pw
import pytest
from playhouse.migrate import Operation

from miggy.state import State

try:
    from playhouse.postgres_ext import Psycopg3Database
except ImportError:  # peewee == 3.17.9
    Psycopg3Database = None

from unittest import mock

from miggy.operations import AddField, CreateModel, MigrateOperation, Migration, RemoveField, RemoveModel
from miggy.router import Router
from tests.conftest import PatchedPgDatabase


def _build_migration(
    router: Router,
    migrate: list[MigrateOperation],
    rollback: list[MigrateOperation],
    atomic: bool = True,
    fake_initial: bool = False,
    name: str = "001_test",
) -> Migration:
    class _Migration(Migration):
        pass

    _Migration.atomic = atomic
    _Migration.fake_initial = fake_initial
    _Migration.forward = migrate
    _Migration.backward = rollback
    return _Migration(name, router.schema_migrator, router.model)


@pytest.mark.parametrize(
    ("fake_initial", "name", "expected"),
    [
        (True, "001_initial", True),
        (True, "002_initial", False),
        (False, "001_initial", False),
    ],
)
def test_is_fake_initial(router: Router, fake_initial: bool, name: str, expected: bool) -> None:
    migration = _build_migration(router, [], [], name=name, fake_initial=fake_initial)

    assert migration.is_fake_initial() is expected


def test_migration_add_operation(router: Router) -> None:
    class User(pw.Model):
        name = pw.CharField()

    router.state["user"] = User

    migration = _build_migration(router, migrate=[], rollback=[])
    operations = migration.add_operation(
        router.state, AddField("user", "email", pw.CharField(max_length=255, null=True))
    )

    user = router.state["user"]
    assert isinstance(user.email, pw.CharField)
    assert user.email.max_length == 255
    assert user.email.null is True
    assert len(operations) == 1
    assert isinstance(operations[0], Operation)


def test_migration_add_operations_not_downgrade(router: Router, patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        name = pw.CharField()
        email = pw.CharField(null=True)

        class Meta:
            database = patched_pg_db

    User.create_table()
    router.state["user"] = User

    migration = _build_migration(
        router,
        migrate=[RemoveField("user", "email")],
        rollback=[],
    )

    operations = migration.add_operations(router.state, backward=False)
    assert len(operations) == 1

    migration.run_operations(operations)
    assert not hasattr(router.state["user"], "email")


def test_migration_add_operations_downgrade(router: Router, patched_pg_db: PatchedPgDatabase) -> None:
    class Order(pw.Model):
        number = pw.CharField()

        class Meta:
            database = patched_pg_db

    Order.create_table()
    router.state["order"] = Order

    migration = _build_migration(
        router,
        migrate=[],
        rollback=[AddField("order", "phone", pw.CharField(null=True))],
    )

    operations = migration.add_operations(router.state, backward=True)
    assert len(operations) == 1

    migration.run_operations(operations)
    assert isinstance(router.state["order"].phone, pw.CharField)


def test_migration_run_operations(router: Router, patched_pg_db: PatchedPgDatabase) -> None:
    class User(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            database = patched_pg_db

    User.create_table()
    router.state["user"] = User
    patched_pg_db.clear_queries()

    migration = _build_migration(router, migrate=[], rollback=[])
    operations = migration.add_operation(router.state, RemoveField("user", "last_name"))
    migration.run_operations(operations)

    assert not hasattr(router.state["user"], "last_name")
    assert patched_pg_db.queries[-1] == 'ALTER TABLE "user" DROP COLUMN "last_name"'


def test_check_all_models_created(router: Router) -> None:

    class Tag(pw.Model):
        tag = pw.CharField()

        class Meta:
            database = router.database

    class Person(pw.Model):
        name = pw.CharField()

        class Meta:
            database = router.database

    migration = _build_migration(router, [], [])
    state = State({Tag._meta.name: Tag, Person._meta.name: Person})

    Tag.create_table()

    assert migration.check_all_models_created(state) is False

    Person.create_table()
    assert migration.check_all_models_created(state) is True


def test_migration_change_history(router: Router) -> None:
    name = "001_test"

    migration = _build_migration(router, migrate=[], rollback=[])
    migration.change_history("001_test", backward=False)

    assert migration.migrate_model.get_or_none(name=name) is not None

    migration.change_history("001_test", backward=True)
    assert migration.migrate_model.get_or_none(name=name) is None


@pytest.mark.parametrize(
    ("change_history", "change_schema"),
    [(True, True), (True, False), (False, False)],
)
def test_apply__change_history_change_schema(router: Router, change_history: bool, change_schema: bool) -> None:
    migration = _build_migration(
        router, migrate=[CreateModel("tag", fields={"tag": pw.CharField()}, meta={})], rollback=[]
    )
    migration.apply(router.state, change_schema=change_schema, change_history=change_history, backward=False)

    assert "tag" in router.state
    assert router.database.table_exists("tag") is change_schema

    assert router.model.select().exists() is change_history


def test_apply__backward(router: Router) -> None:
    migration = _build_migration(
        router, migrate=[CreateModel("tag", fields={"tag": pw.CharField()}, meta={})], rollback=[RemoveModel("tag")]
    )
    migration.apply(router.state, change_schema=True, change_history=True, backward=False)

    assert "tag" in router.state
    assert router.database.table_exists("tag")

    migration.apply(router.state, change_schema=True, change_history=True, backward=True)
    assert "tag" not in router.state
    assert not router.database.table_exists("tag")


@pytest.mark.parametrize(
    ("atomic", "change_schema", "expected"),
    [(True, False, False), (True, True, True), (False, True, False), (False, False, False)],
)
def test_apply_atomic(router: Router, atomic: bool, change_schema: bool, expected: bool) -> None:
    migration = _build_migration(router, migrate=[], rollback=[], atomic=atomic)

    with mock.patch.object(router.database, "transaction") as mocked:
        migration.apply(router.state, change_schema, True, False)

        transaction_called = mocked.call_count == 1
        assert transaction_called is expected


@pytest.mark.parametrize(
    ("fake_initial", "models_created", "expected"),
    [
        (True, False, True),
        (False, False, True),
        (True, True, False),
    ],
)
def test_apply__fake_initial(router: Router, fake_initial: bool, models_created: bool, expected: bool) -> None:

    class Tag(pw.Model):
        tag = pw.CharField()

        class Meta:
            database = router.database

    if models_created:
        Tag.create_table()

    migration = _build_migration(
        router,
        migrate=[CreateModel("tag", fields={"tag": pw.CharField()}, meta={})],
        rollback=[],
        fake_initial=fake_initial,
    )
    migration.apply(router.state, change_schema=True, change_history=True, backward=False)

    q = router.database.queries[-1]
    run_migration = q == 'CREATE TABLE "tag" ("id" SERIAL NOT NULL PRIMARY KEY, "tag" VARCHAR(255) NOT NULL)'
    assert run_migration is expected
