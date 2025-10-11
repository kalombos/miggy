import peewee as pw
import pytest

from peewee_migrate import Migrator
from tests.conftest import PatchedPgDatabase


def test_rename_field(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.rename_field("user", "name", "new_name")
    migrator.run()

    assert patched_pg_db.queries == ['ALTER TABLE "user" RENAME COLUMN "name" TO "new_name"']
    assert not hasattr(migrator.orm["user"], "name")
    assert isinstance(migrator.orm["user"].new_name, pw.CharField)


@pytest.mark.parametrize("object_id_name", [None, "some_name"])
def test_rename_fk_field(patched_pg_db: PatchedPgDatabase, object_id_name: str | None) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    @migrator.create_table
    class Book(pw.Model):
        name = pw.CharField()
        author = pw.ForeignKeyField(User, backref="books", object_id_name=object_id_name)

    migrator.run()
    patched_pg_db.clear_queries()
    migrator.rename_field("book", "author", "new_author")
    migrator.run()

    assert patched_pg_db.queries == ['ALTER TABLE "book" RENAME COLUMN "author_id" TO "new_author_id"']
    assert not hasattr(migrator.orm["book"], "author")
    assert isinstance(migrator.orm["book"].new_author, pw.ForeignKeyField)

    # object_id_name should stay the same
    actual_object_id_name = object_id_name if object_id_name else "author_id"
    assert hasattr(Book, actual_object_id_name)



@pytest.mark.xfail
def test_rename_field_w(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField(column_name="some_other_name")
        created_at = pw.DateField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.rename_field("user", "name", "new_name")
    migrator.run()

    assert patched_pg_db.queries == []
    assert not hasattr(migrator.orm["user"], "name")
    assert isinstance(migrator.orm["user"].new_name, pw.CharField)

# TODO add test for fk with different column name