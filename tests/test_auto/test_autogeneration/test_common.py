import datetime as dt
from pathlib import Path

import peewee as pw
import pytest

from miggy.auto import create_model, diff_many, diff_one, model_to_code
from miggy.cli import get_router
from miggy.types import ModelCls


def test_on_real_migrations(migrations_dir: Path):
    router = get_router(migrations_dir, "sqlite:///:memory:")
    router.run()
    migrator = router.migrator
    models = migrator.orm.values()
    Person_ = migrator.orm["person"]
    Tag_ = migrator.orm["tag"]

    code = model_to_code(Person_)
    assert code
    assert 'table_name = "person"' in code

    changes = diff_many(models, [])
    assert len(changes) == 2

    class Person1(pw.Model):
        first_name = pw.IntegerField()
        last_name = pw.CharField(max_length=1024, null=True, unique=True)
        tag = pw.ForeignKeyField(Tag_, on_delete="CASCADE", backref="persons")
        email = pw.CharField(index=True, unique=True)

        class Meta:
            table_name = "person"

    changes = diff_one(Person1, Person_)
    assert len(changes) == 3
    assert "on_delete='CASCADE'" in changes[0]
    assert "backref='persons'" in changes[0]

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

    class Color(pw.Model):
        id = pw.AutoField()
        name = pw.CharField(default="red")

    code = model_to_code(Color)
    assert "name = pw.CharField(default='red', max_length=255)" in code


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

    code = diff_one(Test, OldTest)[0]
    assert code == "migrator.remove_fields('test', 'age')"


def test_create_model() -> None:
    class Test(pw.Model):
        constraint = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])
        i1 = pw.IntegerField()
        i2 = pw.IntegerField()

        class Meta:
            indexes = ((("i1", "i2"), True),)

    Test.add_index(Test.i1, Test.i2, name="i3")

    changes = diff_many([Test], [])
    create_model_code = changes[0]

    assert create_model_code == create_model(Test)
    assert changes[1] == "migrator.add_index('test', 'i1', 'i2', name='test_i1_i2', unique=True)"
    assert changes[2] == "migrator.add_index('test', 'i1', 'i2', name='i3')"
    assert """constraint = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")], max_length=255)""" in create_model_code


@pytest.mark.parametrize(
    ("name_before", "name_after", "expected"),
    [
        (None, "new_name", ["migrator.rename_table('test', 'new_name')"]),
        (None, "test", []),
        (None, None, []),
        ("new_name", None, ["migrator.rename_table('test', 'test')"]),
    ],
)
def test_rename_table(name_before: str | None, name_after: str | None, expected: list[str]) -> None:
    def create_model(_table_name: str | None) -> ModelCls:
        class Test(pw.Model):
            i1 = pw.IntegerField()

            class Meta:
                table_name = _table_name

        return Test

    changes = diff_one(create_model(name_after), create_model(name_before))
    assert changes == expected

