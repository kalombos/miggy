import os.path as path
import datetime as dt

import peewee as pw
import pytest
from peewee_migrate.auto import diff_one, model_to_code


from peewee_migrate.migrator import Migrator
from playhouse.db_url import connect



@pytest.fixture
def migrator() -> Migrator:
    return Migrator(connect('sqlite:///:memory:'))

def test_add_index(migrator: Migrator) -> None:

    class _Test(pw.Model):
        first_name = pw.CharField()

    class Test(pw.Model):
        first_name = pw.CharField(index=True)

    assert diff_one(Test, _Test, migrator=migrator)[0] == "migrator.add_index('test', 'first_name', unique=False)"


def test_add_unique_index(migrator: Migrator) -> None:

    class _Test(pw.Model):
        first_name = pw.CharField()

    class Test(pw.Model):
        first_name = pw.CharField(index=True, unique=True)

    assert diff_one(Test, _Test, migrator=migrator)[0] == "migrator.add_index('test', 'first_name', unique=True)"


def test_change_to_unqiue_index(migrator: Migrator) -> None:

    class _Test(pw.Model):
        first_name = pw.CharField(index=True)

    class Test(pw.Model):
        first_name = pw.CharField(index=True, unique=True)

    assert diff_one(Test, _Test, migrator=migrator) == ["migrator.drop_index('test', 'first_name')", "migrator.add_index('test', 'first_name', unique=True)"]

def test_change_to_non_unqiue_index(migrator: Migrator) -> None:

    class _Test(pw.Model):
        first_name = pw.CharField(index=True, unique=True)

    class Test(pw.Model):
        first_name = pw.CharField(index=True)

    assert diff_one(Test, _Test, migrator=migrator) == ["migrator.drop_index('test', 'first_name')", "migrator.add_index('test', 'first_name', unique=False)"]


def test_drop_index(migrator: Migrator) -> None:

    class _Test(pw.Model):
        first_name = pw.CharField(index=True)

    class Test(pw.Model):
        first_name = pw.CharField()

    assert diff_one(Test, _Test, migrator=migrator)[0] == "migrator.drop_index('test', 'first_name')"


def test_unique_index__dropped(migrator: Migrator) -> None:

    class _Test(pw.Model):
        first_name = pw.CharField(index=True, unique=True)

    class Test(pw.Model):
        first_name = pw.CharField()

    assert diff_one(Test, _Test, migrator=migrator)[0] == "migrator.drop_index('test', 'first_name')"


@pytest.mark.xfail
def test_composite_index__added(migrator: Migrator) -> None:

    class _Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()


    class Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            indexes = (
                (('first_name', "last_name"), False),
            )
    assert diff_one(Test, _Test, migrator=migrator) == ["migrator.add_index('test', 'first_name', 'last_name', unique=False)"]


@pytest.mark.xfail
def test_composite_unique_index__added(migrator: Migrator) -> None:

    class _Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()


    class Test(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            indexes = (
                (('first_name', "last_name"), True),
            )
    assert diff_one(Test, _Test, migrator=migrator) == ["migrator.add_index('test', 'first_name', 'last_name', unique=True)"]


def test_composite_unique_index__create_model():

    class Object(pw.Model):
        first_name = pw.CharField()
        last_name = pw.CharField()

        class Meta:
            indexes = (
                (('first_name', 'last_name'), True),
            )

    code = model_to_code(Object)
    assert code
    assert "indexes = [(('first_name', 'last_name'), True)]" in code
