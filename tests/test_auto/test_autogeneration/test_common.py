import datetime as dt
from pathlib import Path

import peewee as pw
import pytest

from miggy.auto import diff_many, diff_one
from miggy.cli import get_router
from miggy.operations import AddField, CreateModel
from miggy.types import ModelCls
from miggy.utils import copy_model
from tests.helpers import operation_to_one_line


def test_on_real_migrations(migrations_dir: Path):
    router = get_router(migrations_dir, "sqlite:///:memory:")
    router.run()
    migrator = router.migrator
    models = migrator.state.values()
    Person_ = migrator.state["person"]
    Tag_ = migrator.state["tag"]

    changes = diff_many(models, [])
    assert len(changes) == 2
    assert all(isinstance(c, CreateModel) for c in changes)

    class Person1(pw.Model):
        first_name = pw.IntegerField()
        last_name = pw.CharField(max_length=1024, null=True, unique=True)
        tag = pw.ForeignKeyField(Tag_, on_delete="CASCADE", backref="persons")
        email = pw.CharField(index=True, unique=True)

        class Meta:
            table_name = "person"

    changes = diff_one(Person1, Person_)
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

    changes = diff_one(Person_, Person2)
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

    operation = diff_one(Test, OldTest)[0]
    assert operation_to_one_line(operation) == "migrator.remove_field(model_name='test',name='age',)"  # type: ignore


def test_proper_order_for_fk() -> None:
    def prev_models() -> list[ModelCls]:
        class Users(pw.Model):
            name = pw.TextField()

        return [Users]

    def current_models() -> list[ModelCls]:
        class Test(pw.Model):
            name = pw.TextField()

        class Users(pw.Model):
            name = pw.TextField()
            test = pw.ForeignKeyField(Test, null=True, backref="users")

        return [Test, Users]

    changes = diff_many(current_models(), prev_models())
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
                "migrator.alter_field(model_name='oldtest',name='uid',field=pw.IntegerField(),)",
                "migrator.alter_field(model_name='oldtest',name='guid',field=pw.IntegerField(primary_key=True),)",
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
                "migrator.alter_field(model_name='oldtest',name='guid',field=pw.IntegerField(),)",
                "migrator.alter_field(model_name='oldtest',name='uid',field=pw.IntegerField(primary_key=True),)",
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

    for n, f in fields_before.items():
        OldTest._meta.add_field(n, f)

    Test = copy_model(OldTest)
    for n, f in fields_after.items():
        Test._meta.add_field(n, f)
    diffs = diff_one(Test, OldTest)
    diffs = [operation_to_one_line(o) for o in diffs]  # type: ignore
    assert diffs == expected
