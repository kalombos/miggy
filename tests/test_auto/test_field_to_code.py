import peewee as pw

from peewee_migrate.auto import field_to_code
from peewee_migrate.ext import Default


def test_field_to_code() -> None:
    
    class SomeModel(pw.Model):
        name = pw.CharField(max_length=5, constraints=[Default("some")])

    print(
        field_to_code(SomeModel.name)
    )