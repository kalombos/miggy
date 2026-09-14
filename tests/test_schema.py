import peewee as pw
import pytest
from playhouse.postgres_ext import ArrayField

from miggy.schema import SchemaMigrator
from miggy.utils import ModelIndex, copy_model
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
        # array field
        pytest.param(
            ArrayField(field_class=pw.CharField), ArrayField(field_class=pw.CharField), [], id="array_nothing_changed"
        ),
        pytest.param(
            ArrayField(field_class=pw.CharField),
            ArrayField(field_class=pw.CharField, dimensions=2),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" TYPE VARCHAR(255)[][]'],
            id="array_dimension_changed",
        ),
        pytest.param(
            ArrayField(field_class=pw.CharField),
            ArrayField(field_class=pw.TextField),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" TYPE TEXT[]'],
            id="array_field_type_changed",
        ),
        pytest.param(
            ArrayField(field_class=pw.CharField),
            ArrayField(field_class=pw.CharField, field_kwargs={"max_length": 25}),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" TYPE VARCHAR(25)[]'],
            id="array_modifiers_changed",
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


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.CharField(constraints=[pw.Default("'5'")]),
            pw.CharField(constraints=[pw.Default("'5'")]),
            [],
        ),
        pytest.param(
            pw.CharField(constraints=[pw.Default("'5'")]),
            pw.CharField(constraints=[pw.Default("'6'")]),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" SET DEFAULT \'6\''],
        ),
        pytest.param(
            pw.CharField(),
            pw.CharField(constraints=[pw.Default("'6'")]),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" SET DEFAULT \'6\''],
        ),
        pytest.param(
            pw.CharField(constraints=[pw.Default("'5'")]),
            pw.CharField(),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" DROP DEFAULT'],
        ),
    ],
)
def test__resolve_alter_default_constraint(
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

    schema_migrator._resolve_alter_default_constraint(old_field, new_field).run()

    assert patched_pg_db.queries == expected


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.IntegerField(
                constraints=[pw.SQL("CONSTRAINT up CHECK (price > 5)"), pw.SQL("CONSTRAINT down CHECK (price < 10)")]
            ),
            pw.IntegerField(),
            [
                'ALTER TABLE "oldmodel" DROP CONSTRAINT "down"',
                'ALTER TABLE "oldmodel" DROP CONSTRAINT "up"',
            ],
        ),
        (
            pw.CharField(
                constraints=[
                    pw.Check("price = '5'", name="check_price"),
                ]
            ),
            pw.CharField(
                constraints=[
                    pw.Check("price = '0'", name="check_price"),
                    pw.Check("price = '0'", name="check_price"),
                ]
            ),
            [
                'ALTER TABLE "oldmodel" DROP CONSTRAINT "check_price"',
                'ALTER TABLE "oldmodel" ADD CONSTRAINT "check_price" CHECK (price = \'0\')',
            ],
        ),
        pytest.param(
            pw.IntegerField(
                constraints=[
                    pw.Check("price > 0", name="check_price"),
                ]
            ),
            pw.IntegerField(
                constraints=[
                    pw.Check("price > 0", name="check_price"),
                ]
            ),
            [],
        ),
        pytest.param(
            pw.IntegerField(
                constraints=[
                    pw.Check("price > 0", name="check_price"),
                ]
            ),
            pw.IntegerField(
                constraints=[
                    pw.Check("price > 0", name="new_name"),
                ]
            ),
            [
                'ALTER TABLE "oldmodel" DROP CONSTRAINT "check_price"',
                'ALTER TABLE "oldmodel" ADD CONSTRAINT "new_name" CHECK (price > 0)',
            ],
        ),
    ],
)
def test___resolve_alter_check_constraints(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:

    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    class OldModel(pw.Model):
        price = old_field

        class Meta:
            database = patched_pg_db

    OldModel.create_table()
    NewModel = copy_model(OldModel)

    NewModel._meta.add_field("field", new_field)
    patched_pg_db.clear_queries()

    schema_migrator._resolve_alter_check_constraints(old_field, new_field).run()

    assert patched_pg_db.queries == expected


def test__add_model_index(patched_pg_db: PatchedPgDatabase) -> None:
    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    class Model(pw.Model):
        name = pw.CharField()
        created_at = pw.DateField()

        class Meta:
            database = patched_pg_db

    Model.create_table()
    patched_pg_db.clear_queries()

    model_index = ModelIndex(Model, [Model.name, Model.created_at], name="name_created_at_index", safe=True)

    schema_migrator.add_model_index(model_index).run()

    assert patched_pg_db.queries == [
        'CREATE INDEX IF NOT EXISTS "name_created_at_index" ON "model" ("name", "created_at")'
    ]


class _TestResolveRenameFieldNamespace:
    class User(pw.Model):
        name = pw.CharField()


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.CharField(column_name="field"),
            pw.CharField(column_name="field"),
            [],
            id="same_column_name",
        ),
        pytest.param(
            pw.CharField(column_name="field"),
            pw.CharField(column_name="new_field"),
            ['ALTER TABLE "model" RENAME COLUMN "field" TO "new_field"'],
            id="rename_column",
        ),
        pytest.param(
            pw.CharField(column_name="field", index=True),
            pw.CharField(column_name="new_field", index=True),
            [
                'ALTER TABLE "model" RENAME COLUMN "field" TO "new_field"',
                'ALTER INDEX "model_field" RENAME TO "model_new_field"',
            ],
            id="rename_indexed_column",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestResolveRenameFieldNamespace.User, column_name="author_id"),
            pw.ForeignKeyField(_TestResolveRenameFieldNamespace.User, column_name="new_author_id"),
            [
                'ALTER TABLE "model" RENAME COLUMN "author_id" TO "new_author_id"',
                'ALTER INDEX "model_author_id" RENAME TO "model_new_author_id"',
            ],
            id="rename_fk_column",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestResolveRenameFieldNamespace.User, column_name="some_other_name"),
            pw.ForeignKeyField(_TestResolveRenameFieldNamespace.User, column_name="some_other_name"),
            [],
            id="fk_same_column_name",
        ),
    ],
)
def test__resolve_rename_field(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:
    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    _TestResolveRenameFieldNamespace.User._meta.database = patched_pg_db
    _TestResolveRenameFieldNamespace.User.create_table()

    class Model(pw.Model):
        field = old_field

        class Meta:
            database = patched_pg_db

    Model.create_table()
    NewModel = copy_model(Model)
    NewModel._meta.add_field("field", new_field)
    patched_pg_db.clear_queries()

    schema_migrator.resolve_rename_field("model", Model.field, NewModel.field).run()

    assert patched_pg_db.queries == expected


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.CharField(),
            pw.CharField(),
            [],
            id="no_indexes",
        ),
        pytest.param(
            pw.CharField(unique=True),
            pw.CharField(unique=True),
            [],
            id="same_unique_index",
        ),
        pytest.param(
            pw.CharField(index=True),
            pw.CharField(index=True),
            [],
            id="same_index",
        ),
        pytest.param(
            pw.CharField(),
            pw.CharField(unique=True),
            ['CREATE UNIQUE INDEX "model_field" ON "model" ("field")'],
            id="add_unique_index",
        ),
        pytest.param(
            pw.CharField(unique=True),
            pw.CharField(),
            ['DROP INDEX "model_field"'],
            id="drop_unique_index",
        ),
        pytest.param(
            pw.CharField(),
            pw.CharField(index=True),
            ['CREATE INDEX "model_field" ON "model" ("field")'],
            id="add_index",
        ),
        pytest.param(
            pw.CharField(index=True),
            pw.CharField(),
            ['DROP INDEX "model_field"'],
            id="drop_index",
        ),
        pytest.param(
            pw.CharField(index=True),
            pw.CharField(unique=True),
            [
                'DROP INDEX "model_field"',
                'CREATE UNIQUE INDEX "model_field" ON "model" ("field")',
            ],
            id="index_to_unique",
        ),
        pytest.param(
            pw.CharField(unique=True),
            pw.CharField(index=True),
            [
                'DROP INDEX "model_field"',
                'CREATE INDEX "model_field" ON "model" ("field")',
            ],
            id="unique_to_index",
        ),
    ],
)
def test__resolve_alter_indexes(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:
    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    class Model(pw.Model):
        field = old_field

        class Meta:
            database = patched_pg_db

    Model.create_table()
    NewModel = copy_model(Model)
    NewModel._meta.add_field("field", new_field)
    patched_pg_db.clear_queries()

    schema_migrator._resolve_alter_indexes(Model.field, NewModel.field).run()

    assert patched_pg_db.queries == expected


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.CharField(null=True),
            pw.CharField(null=True),
            [],
            id="both_null",
        ),
        pytest.param(
            pw.CharField(),
            pw.CharField(),
            [],
            id="both_not_null",
        ),
        pytest.param(
            pw.CharField(),
            pw.CharField(null=True),
            ['ALTER TABLE "model" ALTER COLUMN "field" DROP NOT NULL'],
            id="drop_not_null",
        ),
        pytest.param(
            pw.CharField(null=True),
            pw.CharField(),
            ['ALTER TABLE "model" ALTER COLUMN "field" SET NOT NULL'],
            id="add_not_null",
        ),
    ],
)
def test__resolve_alter_nullable(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:
    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    class Model(pw.Model):
        field = old_field

        class Meta:
            database = patched_pg_db

    Model.create_table()
    NewModel = copy_model(Model)
    NewModel._meta.add_field("field", new_field)
    patched_pg_db.clear_queries()

    schema_migrator._resolve_alter_nullable(Model.field, NewModel.field).run()

    assert patched_pg_db.queries == expected


class _TestResolveAlterFkConstraintNamespace:
    class RefModel(pw.Model):
        another_id = pw.IntegerField(unique=True, column_name="another_column_name")


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.ForeignKeyField(_TestResolveAlterFkConstraintNamespace.RefModel),
            pw.ForeignKeyField(_TestResolveAlterFkConstraintNamespace.RefModel, field="another_id"),
            [
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_some_field_id_fkey"',
                'ALTER TABLE "testmodel" ADD CONSTRAINT '
                '"fk_testmodel_some_field_id_refs_refmodel" FOREIGN KEY ("some_field_id") '
                'REFERENCES "refmodel" ("another_column_name")',
            ],
            id="column_name_is_used_from_rel_field",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestResolveAlterFkConstraintNamespace.RefModel),
            pw.ForeignKeyField(_TestResolveAlterFkConstraintNamespace.RefModel, on_delete="RESTRICT"),
            [
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_some_field_id_fkey"',
                'ALTER TABLE "testmodel" ADD CONSTRAINT '
                '"fk_testmodel_some_field_id_refs_refmodel" FOREIGN KEY ("some_field_id") '
                'REFERENCES "refmodel" ("id") ON DELETE RESTRICT',
            ],
            id="update_on_delete",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestResolveAlterFkConstraintNamespace.RefModel),
            pw.ForeignKeyField(_TestResolveAlterFkConstraintNamespace.RefModel, constraint_name="some_name"),
            [
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_some_field_id_fkey"',
                'ALTER TABLE "testmodel" ADD CONSTRAINT "some_name" FOREIGN KEY '
                '("some_field_id") REFERENCES "refmodel" ("id")',
            ],
            id="constraint_name",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestResolveAlterFkConstraintNamespace.RefModel, on_update="RESTRICT"),
            pw.ForeignKeyField(_TestResolveAlterFkConstraintNamespace.RefModel, on_update="RESTRICT"),
            [],
            id="same_fields",
        ),
    ],
)
def test__resolve_alter_fk_constraint(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:
    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    ref_model = _TestResolveAlterFkConstraintNamespace.RefModel
    ref_model._meta.database = patched_pg_db
    ref_model.create_table()

    class TestModel(pw.Model):
        whatever_field = pw.CharField()

        class Meta:
            database = patched_pg_db

    TestModel._meta.add_field("some_field", old_field)
    TestModel.create_table()
    NewTestModel = copy_model(TestModel)
    NewTestModel._meta.add_field("some_field", new_field)
    patched_pg_db.clear_queries()

    schema_migrator._resolve_alter_fk_constraint(TestModel.some_field, NewTestModel.some_field).run()

    # remove query for constraints
    queries = [q for q in patched_pg_db.queries if "FROM information_schema.table_constraints" not in q]
    assert queries == expected


def test__resolve_alter_fk_constraint_column_is_renamed(patched_pg_db: PatchedPgDatabase) -> None:
    schema_migrator = SchemaMigrator.from_database(patched_pg_db)

    ref_model = _TestResolveAlterFkConstraintNamespace.RefModel
    ref_model._meta.database = patched_pg_db
    ref_model.create_table()

    old_field = pw.ForeignKeyField(ref_model)
    new_field = pw.ForeignKeyField(ref_model, on_delete="RESTRICT", column_name="is_used")

    class TestModel(pw.Model):
        whatever_field = pw.CharField()

        class Meta:
            database = patched_pg_db

    TestModel._meta.add_field("some_field", old_field)
    TestModel.create_table()

    # Emulate that the column has been renamed before, as in AlterField.database_forwards
    schema_migrator.rename_column("testmodel", "some_field_id", "is_used").run()
    NewTestModel = copy_model(TestModel)
    NewTestModel._meta.add_field("some_field", new_field)
    patched_pg_db.clear_queries()

    schema_migrator._resolve_alter_fk_constraint(TestModel.some_field, NewTestModel.some_field).run()

    # remove query for constraints
    queries = [q for q in patched_pg_db.queries if "FROM information_schema.table_constraints" not in q]
    assert queries == [
        'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_some_field_id_fkey"',
        'ALTER TABLE "testmodel" ADD CONSTRAINT '
        '"fk_testmodel_is_used_refs_refmodel" FOREIGN KEY ("is_used") REFERENCES '
        '"refmodel" ("id") ON DELETE RESTRICT',
    ]
