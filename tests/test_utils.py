from typing import Any

import peewee as pw
import pytest

from peewee_migrate.utils import Default, copy_model, delete_field, get_default_constraint


@pytest.mark.parametrize(
    ("field_params", "expected"),
    [
        ({}, None),
        ({"constraints": [Default("'couple words'"), pw.Check("price > 0")]}, "'couple words'"),
        ({"constraints": [pw.SQL("DEFAULT 5"), pw.Check("price > 0")]}, "5"),
    ],
)
def test_get_default_constraint(field_params: dict[str, Any], expected: str) -> None:
    class User(pw.Model):
        name = pw.CharField(**field_params)

    default = get_default_constraint(User.name)
    value = default.value if isinstance(default, Default) else None

    assert value == expected


def test_get_default_constraint__error() -> None:
    class User(pw.Model):
        name = pw.CharField(constraints=[Default("5"), pw.SQL("DEFAULT 10")])

    with pytest.raises(ValueError):
        get_default_constraint(User.name)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (pw.SQL("DEFAULT now()"), "now()"),
        (pw.SQL(" DEFAULT 5"), "5"),
        (pw.SQL(" DEFAULT 'two words'"), "'two words'"),
        (pw.SQL("DEFAULT 5", params=["5"]), None),
        (pw.SQL("EFAULT 5"), None),
        (pw.SQL("DEFAULT    "), None),
        (pw.SQL("DEFAULT "), None),
        (pw.SQL("DEFAULT"), None),
    ],
)
def test_default__from_sql(sql: pw.SQL, expected: str) -> None:
    default = Default.from_SQL(sql)
    value = default.value if isinstance(default, Default) else None
    assert value == expected


def test_delete_field() -> None:
    class SomeModel(pw.Model):
        some_field = pw.CharField()

    class User(pw.Model):
        my_pk = pw.CharField(primary_key=True)
        fk = pw.ForeignKeyField(SomeModel, backref="users")

    delete_field(User, User.my_pk)
    delete_field(User, User.fk)

    assert not hasattr(SomeModel, "users")
    assert not hasattr(User, "my_pk")
    assert not hasattr(User, "fk_id")


def test_copy_model() -> None:
    class User(pw.Model):
        my_pk = pw.CharField(primary_key=True)
        name = pw.CharField(constraints=[Default("5"), pw.SQL("DEFAULT 10")])

    NewModel = copy_model(User)

    delete_field(User, User.my_pk)
    User.name.constriants = []

    assert NewModel.__name__ == "User"
    assert isinstance(NewModel.my_pk, pw.CharField)
    assert NewModel.my_pk.primary_key
    assert [Default, pw.SQL] == [type(c) for c in NewModel.name.constraints]
