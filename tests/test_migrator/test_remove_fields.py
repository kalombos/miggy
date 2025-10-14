import peewee as pw
import pytest

from peewee_migrate import Migrator
from tests.conftest import PatchedPgDatabase


def test_remove_fields(patched_pg_db: PatchedPgDatabase) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        # also check if it is ok to drop field without dropping indexes before
        name = pw.CharField(unique=True)
        created_at = pw.DateField()

    migrator.run()
    patched_pg_db.clear_queries()

    migrator.remove_fields("user", "name", "created_at")
    migrator.run()

    alter_queries = [
        patched_pg_db.queries[1],
        patched_pg_db.queries[3],
    ]

    assert alter_queries == ['ALTER TABLE "user" DROP COLUMN "name"', 'ALTER TABLE "user" DROP COLUMN "created_at"']
    assert not hasattr(migrator.orm["user"], "name")
    assert not hasattr(migrator.orm["user"], "created_at")


@pytest.mark.parametrize("object_id_name", [None, "some_name"])
def test_remove_fk_field(patched_pg_db: PatchedPgDatabase, object_id_name: str | None) -> None:
    migrator = Migrator(patched_pg_db)

    @migrator.create_table
    class User(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

    @migrator.create_table
    class Book(pw.Model):
        name = pw.CharField()
        author = pw.ForeignKeyField(User, backref="books", object_id_name=object_id_name)

    actual_object_id_name = object_id_name if object_id_name else "author_id"
    assert hasattr(Book, actual_object_id_name)

    migrator.run()
    patched_pg_db.clear_queries()
    migrator.remove_fields("book", "author")
    migrator.run()

    _, alter_query = patched_pg_db.queries
    assert alter_query == 'ALTER TABLE "book" DROP COLUMN "author_id"'
    assert not hasattr(migrator.orm["book"], "author")
    assert not hasattr(migrator.orm["book"], actual_object_id_name)
    assert not hasattr(migrator.orm["user"], "books")
