import datetime as dt
from pathlib import Path

import peewee as pw
import pytest

from miggy.auto import MigrationAutodetector
from miggy.cli import get_router
from miggy.operations import AddField, CreateModel
from miggy.state import State
from miggy.utils import copy_model
from tests.helpers import diff_one, operation_to_one_line


def test_on_real_migrations(migrations_dir: Path):
    router = get_router(migrations_dir, "sqlite:///:memory:")
    router.run()
    migrator = router.migrator
    Person_ = migrator.state["person"]
    Tag_ = migrator.state["tag"]

    changes = MigrationAutodetector(State(), migrator.state).diff_many()
    assert len(changes) == 2
    assert all(isinstance(c, CreateModel) for c in changes)

    class Person1(pw.Model):
        first_name = pw.IntegerField()
        last_name = pw.CharField(max_length=1024, null=True, unique=True)
        tag = pw.ForeignKeyField(Tag_, on_delete="CASCADE", backref="persons")
        email = pw.CharField(index=True, unique=True)

        class Meta:
            table_name = "person"

    changes = diff_one(Person_, Person1)
    assert len(changes) == 5
    assert isinstance(changes[0], AddField)

    class Person2(pw.Model):
        first_name = pw.CharField(max_length=255)
        last_name = pw.CharField(max_length=255, index=True)
        dob = pw.DateField(null=True)
        birthday = pw.DateField(default=dt.datetime.now)
        email = pw.CharField(index=True, unique=True)

        class Meta:
            table_name = "person"

    changes = diff_one(Person2, Person_)
    assert not changes


def test_drop_field_w_constraint() -> None:
    class OldTest(pw.Model):
        first_name = pw.CharField()
        age = pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])

        class Meta:
            table_name = "test"

    class Test(pw.Model):
        first_name = pw.CharField()

        class Meta:
            table_name = "test"

    operation = diff_one(OldTest, Test)[0]
    assert operation_to_one_line(operation) == "migrator.remove_field(model_name='test',name='age',)"  # type: ignore


def test_proper_order_for_fk() -> None:
    def from_state() -> State:
        class Users(pw.Model):
            name = pw.TextField()

        return State({"users": Users})

    def to_state() -> State:
        class Test(pw.Model):
            name = pw.TextField()

        class Users(pw.Model):
            name = pw.TextField()
            test = pw.ForeignKeyField(Test, null=True, backref="users")

        return State({"test": Test, "users": Users})

    changes = MigrationAutodetector(from_state(), to_state()).diff_many()
    # we create model first
    assert isinstance(changes[0], CreateModel)
    # we add fk to it after
    assert isinstance(changes[1], AddField)


@pytest.mark.parametrize(
    ("fields_before", "fields_after", "expected"),
    [
        pytest.param(
            {
                "age": pw.IntegerField(),
                "uid": pw.IntegerField(primary_key=True),
                "name": pw.CharField(),
                "guid": pw.IntegerField(),
            },
            {
                "age": pw.IntegerField(),
                "uid": pw.IntegerField(),
                "name": pw.CharField(),
                "guid": pw.IntegerField(primary_key=True),
            },
            [
                "migrator.alter_field(model_name='test',name='uid',field=pw.IntegerField(),)",
                "migrator.alter_field(model_name='test',name='guid',field=pw.IntegerField(primary_key=True),)",
            ],
        ),
        pytest.param(
            {
                "age": pw.IntegerField(),
                "uid": pw.IntegerField(),
                "name": pw.CharField(),
                "guid": pw.IntegerField(primary_key=True),
            },
            {
                "age": pw.IntegerField(),
                "uid": pw.IntegerField(primary_key=True),
                "name": pw.CharField(),
                "guid": pw.IntegerField(),
            },
            [
                "migrator.alter_field(model_name='test',name='guid',field=pw.IntegerField(),)",
                "migrator.alter_field(model_name='test',name='uid',field=pw.IntegerField(primary_key=True),)",
            ],
        ),
        pytest.param(
            {
                "id": pw.AutoField(),
                "uid": pw.IntegerField(),
            },
            {
                "uid": pw.IntegerField(primary_key=True),
            },
            [
                "migrator.remove_field(model_name='test',name='id',)",
                "migrator.alter_field(model_name='test',name='uid',field=pw.IntegerField(primary_key=True),)",
            ],
        ),
        pytest.param(
            {
                "uid": pw.IntegerField(primary_key=True),
            },
            {
                "id": pw.AutoField(),
                "uid": pw.IntegerField(),
            },
            [
                "migrator.alter_field(model_name='test',name='uid',field=pw.IntegerField(),)",
                "migrator.add_field(model_name='test',name='id',field=pw.AutoField(),)",
            ],
        ),
    ],
)
def test_primary_key_order(
    fields_before: dict[str, pw.Field], fields_after: dict[str, pw.Field], expected: list[str]
) -> None:
    class OldTest(pw.Model):
        mock_field = pw.CharField()

        class Meta:
            table_name = "test"
            primary_key = False

    Test = copy_model(OldTest)

    def make_from_state() -> State:
        s = State({"test": OldTest})
        for n, f in fields_before.items():
            s.add_field("test", n, f)
        return s

    def make_to_state() -> State:
        s = State({"test": Test})
        for n, f in fields_after.items():
            s.add_field("test", n, f)
        return s

    diffs = MigrationAutodetector(make_from_state(), make_to_state()).diff_one("test")
    diffs = [operation_to_one_line(o) for o in diffs]  # type: ignore
    assert diffs == expected
