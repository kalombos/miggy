import peewee as pw
import pytest

from miggy.schema import SchemaMigrator
from miggy.utils import copy_model
from tests.conftest import PatchedPgDatabase


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.IntegerField(primary_key=False),
            pw.IntegerField(primary_key=False),
            [],
            id="both_not_pk",
        ),
        pytest.param(
            pw.IntegerField(primary_key=True),
            pw.IntegerField(primary_key=True),
            [],
            id="both_pk",
        ),
        pytest.param(
            pw.IntegerField(primary_key=True),
            pw.IntegerField(primary_key=False),
            ['ALTER TABLE "oldmodel" DROP CONSTRAINT "oldmodel_pkey"'],
            id="drop_pk",
        ),
        pytest.param(
            pw.IntegerField(primary_key=False),
            pw.IntegerField(primary_key=True),
            ['ALTER TABLE "oldmodel" ADD PRIMARY KEY ("field")'],
            id="add_pk",
        ),
    ],
)
def test__change_primary_key(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:

    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    class OldModel(pw.Model):
        field = old_field

        class Meta:
            primary_key = False
            database = patched_pg_db

    OldModel.create_table()
    NewModel = copy_model(OldModel)

    NewModel._meta.add_field("field", new_field)
    patched_pg_db.clear_queries()

    schema_migrator._change_primary_key(old_field, new_field).run()

    queries = [q for q in patched_pg_db.queries if "FROM pg_constraint" not in q]
    assert queries == expected
