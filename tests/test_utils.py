from typing import Any

import peewee as pw
import pytest

from peewee_migrate.ext import Default
from peewee_migrate.utils import get_default_constraint


@pytest.mark.parametrize(
    ("field_params", "expected"),
    [
        ({}, None),
        ({"constraints": [Default("'couple words'"), pw.Check("price > 0")]}, "'couple words'"),
        ({"constraints": [pw.SQL("DEFAULT 5"), pw.Check("price > 0")]}, "5"),
    ]
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
