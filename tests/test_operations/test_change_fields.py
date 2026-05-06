import peewee as pw
import pytest

from miggy.operations import ChangeFields
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    class User(pw.Model):
        test = pw.CharField()

    state = State()
    state["user"] = User

    operation = ChangeFields(
        "User",
        **{
            "name": pw.CharField(max_length=100),
            "email": pw.CharField(max_length=255, null=True),
        },
    )

    operation.state_forwards(state)

    model = state["user"]

    assert isinstance(model.email, pw.CharField)
    assert isinstance(model.name, pw.CharField)


class _TestHandleFkConstraintNamespace:
    class RefModel(pw.Model):
        another_id = pw.IntegerField(unique=True, column_name="another_column_name")


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.ForeignKeyField(_TestHandleFkConstraintNamespace.RefModel),
            pw.ForeignKeyField(_TestHandleFkConstraintNamespace.RefModel, field="another_id"),
            [
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_some_field_id_fkey"',
                'ALTER TABLE "testmodel" ADD CONSTRAINT '
                '"fk_testmodel_some_field_id_refs_refmodel" FOREIGN KEY ("some_field_id") '
                'REFERENCES "refmodel" ("another_column_name")',
            ],
            id="column_name_is_used_from_rel_field",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestHandleFkConstraintNamespace.RefModel),
            pw.ForeignKeyField(_TestHandleFkConstraintNamespace.RefModel, on_delete="RESTRICT"),
            [
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_some_field_id_fkey"',
                'ALTER TABLE "testmodel" ADD CONSTRAINT '
                '"fk_testmodel_some_field_id_refs_refmodel" FOREIGN KEY ("some_field_id") '
                'REFERENCES "refmodel" ("id") ON DELETE RESTRICT',
            ],
            id="update_on_delete",
        ),
        # TODO add test somehow
        # pytest.param(
        #     pw.ForeignKeyField(_TestHandleFkConstraintNamespace.RefModel, ),
        #     pw.ForeignKeyField(_TestHandleFkConstraintNamespace.RefModel, on_delete="RESTRICT",
        #      column_name="is_used"),
        #     [
        #         'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_is_used_fkey"',
        #         'ALTER TABLE "testmodel" ADD CONSTRAINT '
        #         '"fk_testmodel_is_used_refs_refmodel" FOREIGN KEY ("is_used") REFERENCES '
        #         '"refmodel" ("id") ON DELETE RESTRICT',
        #     ],
        #     id="column_name_is_used_from_new_field_for_drop_constraint",
        # ),
        pytest.param(
            pw.ForeignKeyField(
                _TestHandleFkConstraintNamespace.RefModel,
            ),
            pw.ForeignKeyField(
                _TestHandleFkConstraintNamespace.RefModel,
                constraint_name="some_name",
            ),
            [
                'ALTER TABLE "testmodel" DROP CONSTRAINT "testmodel_some_field_id_fkey"',
                'ALTER TABLE "testmodel" ADD CONSTRAINT "some_name" FOREIGN KEY '
                '("some_field_id") REFERENCES "refmodel" ("id")',
            ],
            id="constarint_name",
        ),
        pytest.param(
            pw.ForeignKeyField(_TestHandleFkConstraintNamespace.RefModel, on_update="RESTRICT"),
            pw.ForeignKeyField(
                _TestHandleFkConstraintNamespace.RefModel,
                on_update="RESTRICT",
            ),
            [],
            id="same_fields",
        ),
    ],
)
def test_handle_fk_constraint(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:
    _TestHandleFkConstraintNamespace.RefModel._meta.database = patched_pg_db
    _TestHandleFkConstraintNamespace.RefModel.create_table()

    class TestModel(pw.Model):
        whatever_field = pw.CharField()

        class Meta:
            database = patched_pg_db

    TestModel._meta.add_field("some_field", old_field)
    TestModel.create_table()

    TestModel._meta.add_field("some_field", new_field)

    patched_pg_db.clear_queries()
    operation = ChangeFields("User")

    for o in operation.handle_fk_constraint(old_field, new_field, SchemaMigrator.from_database(patched_pg_db)):
        o.run()
    # remove query for constraints
    queries = [q for q in patched_pg_db.queries if "FROM information_schema.table_constraints" not in q]
    assert queries == expected
