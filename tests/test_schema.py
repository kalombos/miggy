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
def test__resolve_alter_primary_key(
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

    schema_migrator._resolve_alter_primary_key(old_field, new_field).run()

    queries = [q for q in patched_pg_db.queries if "FROM pg_constraint" not in q]
    assert queries == expected


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        pytest.param(pw.IntegerField(null=True), ['ALTER TABLE "model" ADD COLUMN "field" INTEGER'], id="null"),
        pytest.param(
            pw.IntegerField(default=6),
            [
                'ALTER TABLE "model" ADD COLUMN "field" INTEGER',
                'UPDATE "model" SET "field" = 6',
                'ALTER TABLE "model" ALTER COLUMN "field" SET NOT NULL',
            ],
            id="default",
        ),
        pytest.param(
            pw.AutoField(),
            [
                'ALTER TABLE "model" ADD COLUMN "field" SERIAL PRIMARY KEY',
                'ALTER TABLE "model" ALTER COLUMN "field" SET NOT NULL',
            ],
        ),
        pytest.param(
            pw.IntegerField(constraints=[pw.SQL(" DEFAULT 5")]),
            [
                'ALTER TABLE "model" ADD COLUMN "field" INTEGER  DEFAULT 5',
                'ALTER TABLE "model" ALTER COLUMN "field" SET NOT NULL',
            ],
        ),
        pytest.param(
            pw.IntegerField(sequence="test_sequence"),
            [
                'ALTER TABLE "model" ADD COLUMN "field" INTEGER DEFAULT NEXTVAL(\'test_sequence\')',
                'ALTER TABLE "model" ALTER COLUMN "field" SET NOT NULL',
            ],
        ),
    ],
)
def test__add_field(field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]) -> None:

    schema_migrator = SchemaMigrator.from_database(patched_pg_db)
    patched_pg_db.execute_sql("""CREATE SEQUENCE test_sequence START 500""")

    class Model(pw.Model):
        some_field = pw.CharField()

        class Meta:
            primary_key = False
            database = patched_pg_db

    Model.create_table()
    Model.create(some_field="some_field")

    Model._meta.add_field("field", field)
    patched_pg_db.clear_queries()

    schema_migrator.add_field(Model.field).run()

    assert patched_pg_db.queries == expected


def test__add_field__error(patched_pg_db: PatchedPgDatabase) -> None:

    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    class Model(pw.Model):
        some_field = pw.CharField()

    Model._meta.add_field("field", pw.IntegerField())
    with pytest.raises(ValueError):
        schema_migrator.add_field(Model.field).run()


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.CharField(),
            pw.CharField(),
            [],
        ),
        pytest.param(
            pw.DecimalField(),
            pw.DecimalField(),
            [],
        ),
        pytest.param(
            pw.DecimalField(),
            pw.DecimalField(max_digits=5),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" TYPE NUMERIC(5, 5)'],
        ),
        pytest.param(
            pw.SmallIntegerField(),
            pw.IntegerField(),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" TYPE INTEGER'],
        ),
        pytest.param(
            pw.CharField(max_length=55),
            pw.CharField(),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" TYPE VARCHAR(255)'],
        ),
    ],
)
def test__resolve_alter_column_type(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:

    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    class OldModel(pw.Model):
        field = old_field

        class Meta:
            database = patched_pg_db

    OldModel.create_table()
    NewModel = copy_model(OldModel)

    NewModel._meta.add_field("field", new_field)
    patched_pg_db.clear_queries()

    schema_migrator._resolve_alter_column_type(old_field, new_field).run()

    assert patched_pg_db.queries == expected
