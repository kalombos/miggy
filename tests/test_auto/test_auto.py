import peewee as pw

from peewee_migrate.auto import field_to_code


def test_field_to_code() -> None:
    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[pw.SQL("DEFAULT 'Some'")])

    assert field_to_code(SomeModel.name) == (
        """name = pw.CharField(constraints=[pw.SQL("DEFAULT 'Some'")], max_length=5)"""
    )
