import peewee as pw
import pytest

from peewee_migrate.ext import Default


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            pw.SQL("DEFAULT now()"), "now()"
        ),
        (
            pw.SQL(" DEFAULT 5"), "5"
        ),
        (
            pw.SQL(" DEFAULT 'two words'"), "'two words'"
        ),
        (
            pw.SQL("DEFAULT 5", params=["5"]), None
        ),
        (
            pw.SQL("EFAULT 5"), None
        ),
    ],
)
def test_default__from_sql(sql: pw.SQL, expected: str) -> None:
    default = Default.from_SQL(sql)
    value = default.value if isinstance(default, Default) else None
    assert value == expected