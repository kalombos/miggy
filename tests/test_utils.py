from typing import Any

import peewee as pw
import pytest

from miggy.utils import CheckMeta, DefaultMeta, copy_model, extract_check_meta, extract_default_meta


@pytest.mark.parametrize(
    ("field_params", "expected"),
    [
        ({}, None),
        ({"constraints": [pw.Default("'couple words'"), pw.Check("price > 0")]}, DefaultMeta(value="'couple words'")),
        ({"constraints": [pw.SQL("DEFAULT 5"), pw.Check("price > 0")]}, DefaultMeta(value="5")),
    ],
)
def test_extract_default_meta(field_params: dict[str, Any], expected: str) -> None:
    class User(pw.Model):
        name = pw.CharField(**field_params)

    default = extract_default_meta(User.name)

    assert default == expected


@pytest.mark.parametrize(
    ("field_params", "expected"),
    [
        ({}, []),
        (
            {
                "constraints": [
                    pw.Check("price > 0", name="plus"),
                    pw.Check("price > 0", name="plus"),
                    pw.Check("price < 100", name="minus"),
                ]
            },
            [CheckMeta("minus", "price < 100"), CheckMeta("plus", "price > 0")],
        ),  # no doubles,
        (
            {
                "constraints": [
                    pw.Check("price < 100", name="minus"),
                    pw.Check("price > 0", name="plus"),
                ]
            },
            [CheckMeta("minus", "price < 100"), CheckMeta("plus", "price > 0")],
        ),  # same order
    ],
)
def test_extract_check_meta(field_params: dict[str, Any], expected: str) -> None:
    class User(pw.Model):
        name = pw.CharField(**field_params)

    default = extract_check_meta(User.name)

    assert default == expected


def test_extract_default_meta__error() -> None:
    class User(pw.Model):
        name = pw.CharField(constraints=[pw.Default("5"), pw.SQL("DEFAULT 10")])

    with pytest.raises(ValueError):
        extract_default_meta(User.name)


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
def test_default__from_node(sql: pw.SQL, expected: str) -> None:
    default = DefaultMeta.from_node(sql)
    value = default.value if isinstance(default, DefaultMeta) else None
    assert value == expected


@pytest.mark.parametrize(
    ("node", "expected"),
    [
        (pw.Check("price > 0", name="check_price"), CheckMeta(name="check_price", constraint="price > 0")),
        (
            pw.SQL('CONSTRAINT "check_price" CHECK   (price > 10)'),
            CheckMeta(name="check_price", constraint="price > 10"),
        ),
        (
            pw.SQL("CONSTRAINT check_price CHECK   (price > 10)"),
            CheckMeta(name="check_price", constraint="price > 10"),
        ),
    ],
)
def test_check_meta_from_node(node: pw.Node, expected: str) -> None:
    assert CheckMeta.from_node(node) == expected


def test_check_meta_from_node_unnamed() -> None:
    with pytest.raises(ValueError):
        CheckMeta.from_node(pw.Check("price > 10"))


def test_copy_model() -> None:
    class User(pw.Model):
        my_pk = pw.CharField(primary_key=True)
        name = pw.CharField(constraints=[pw.Default("5"), pw.Check("name > 0", name="some_name")])

    NewModel = copy_model(User)

    User._meta.remove_field("my_pk")
    User.name.constriants = []

    assert NewModel.__name__ == "User"
    assert isinstance(NewModel.my_pk, pw.CharField)
    assert NewModel.my_pk.primary_key
    default, check = NewModel.name.constraints
    assert DefaultMeta.from_node(default) == DefaultMeta("5")
    assert CheckMeta.from_node(check) == CheckMeta(name="some_name", constraint="name > 0")
