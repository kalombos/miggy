from typing import Any

import peewee as pw
import pytest

from peewee_migrate.utils import Default, get_default_constraint


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
