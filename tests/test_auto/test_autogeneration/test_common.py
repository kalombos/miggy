import datetime as dt
from pathlib import Path

import peewee as pw
from playhouse.postgres_ext import (
    ArrayField,
    BinaryJSONField,
    DateTimeTZField,
    HStoreField,
    IntervalField,
    JSONField,
    TSVectorField,
)

from peewee_migrate.auto import create_model, diff_many, diff_one, model_to_code
from peewee_migrate.cli import get_router
from peewee_migrate.migrator import Migrator
from peewee_migrate.types import Model


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

    changes = diff_many(models, [], migrator=migrator)
    assert len(changes) == 2

    class Person1(Model):
        first_name = pw.IntegerField()
        last_name = pw.CharField(max_length=1024, null=True, unique=True)
        tag = pw.ForeignKeyField(Tag_, on_delete="CASCADE", backref="persons")
        email = pw.CharField(index=True, unique=True)

        class Meta:
            table_name = "person"

    changes = diff_one(Person1, Person_, migrator=migrator)
    assert len(changes) == 3
    assert "on_delete='CASCADE'" in changes[0]
    assert "backref='persons'" in changes[0]

    migrator.drop_index("person", "email")
    migrator.add_index("person", "email", unique=True)

    class Person2(Model):
        first_name = pw.CharField(unique=True)
        last_name = pw.CharField(max_length=255, index=True)
        dob = pw.DateField(null=True)
        birthday = pw.DateField(default=dt.datetime.now)
        email = pw.CharField(index=True, unique=True)

        class Meta:
            table_name = "person"

    changes = diff_one(Person_, Person2, migrator=migrator)
    assert not changes

    class Color(pw.Model):
        id = pw.AutoField()
        name = pw.CharField(default="red")

    code = model_to_code(Color)
    assert "name = pw.CharField(default='red', max_length=255)" in code


def test_remove_fields_w_constraint(sq_migrator: Migrator) -> None:
    class Test(Model):
        first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])

    code = diff_many([Test], [], migrator=sq_migrator)[0]
    assert code == create_model(Test)
    assert """first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")], max_length=255)""" in code


def test_drop_field_w_constraint(sq_migrator: Migrator) -> None:
    class OldTest(Model):
        first_name = pw.CharField()
        age = pw.IntegerField(constraints=[pw.SQL("DEFAULT 5")])

        class Meta:
            table_name = "test"

    class Test(Model):
        first_name = pw.CharField()

        class Meta:
            table_name = "test"

    code = diff_one(Test, OldTest, migrator=sq_migrator)[0]
    assert code == "migrator.remove_fields('test', 'age')"


def test_auto_postgresext():
    class Object(pw.Model):
        array_field = ArrayField()
        binary_json_field = BinaryJSONField()
        dattime_tz_field = DateTimeTZField()
        hstore_field = HStoreField()
        interval_field = IntervalField()
        json_field = JSONField()
        ts_vector_field = TSVectorField()

    code = model_to_code(Object)
    assert code
    assert "json_field = pw_pext.JSONField()" in code
    assert "hstore_field = pw_pext.HStoreField(index=True)" in code
