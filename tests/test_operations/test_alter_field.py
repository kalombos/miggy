import peewee as pw
import pytest

from miggy.operations import AlterField
from miggy.schema import SchemaMigrator
from miggy.state import State
from miggy.utils import copy_model
from tests.conftest import PatchedPgDatabase
from tests.helpers import run_operations


def test_state_forwards() -> None:
    class User(pw.Model):
        test = pw.CharField()

    state = State()
    state["user"] = User

    operation = AlterField(
        "User",
        "test",
        pw.CharField(max_length=100),
    )

    operation.state_forwards(state)

    model = state["user"]

    assert model.test.max_length == 100


@pytest.mark.parametrize(
    ("old_field", "new_field", "expected"),
    [
        pytest.param(
            pw.IntegerField(primary_key=False),
            pw.IntegerField(primary_key=True),
            ['ALTER TABLE "oldmodel" ADD PRIMARY KEY ("field")'],
            id="pk_constraint",
        ),
        pytest.param(
            pw.CharField(), pw.TextField(), ['ALTER TABLE "oldmodel" ALTER COLUMN "field" TYPE TEXT'], id="type"
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(constraints=[pw.Default(5)]),
            ['ALTER TABLE "oldmodel" ALTER COLUMN "field" SET DEFAULT 5'],
            id="default_constraint",
        ),
        pytest.param(
            pw.IntegerField(),
            pw.IntegerField(constraints=[pw.Check("field > 5", name="check")]),
            ['ALTER TABLE "oldmodel" ADD CONSTRAINT "check" CHECK (field > 5)'],
            id="check_constraint",
        ),
    ],
)
def test__database_forwards(
    old_field: pw.Field, new_field: pw.Field, patched_pg_db: PatchedPgDatabase, expected: list[str]
) -> None:

    class OldModel(pw.Model):
        field = old_field

        class Meta:
            primary_key = False
            database = patched_pg_db

    OldModel.create_table()
    patched_pg_db.clear_queries()
    NewModel = copy_model(OldModel)
    NewModel._meta.add_field("field", new_field)

    operation = AlterField(
        "oldmodel",
        name="field",
        field=new_field,
    )

    from_state = State({"oldmodel": OldModel})
    to_state = State({"oldmodel": NewModel})

    run_operations(operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), from_state, to_state))

    queries = [q for q in patched_pg_db.queries if "FROM pg_constraint" not in q]
    assert queries == expected
