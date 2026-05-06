import peewee as pw

from miggy.operations import CreateModel
from miggy.schema import SchemaMigrator
from miggy.state import State
from tests.conftest import PatchedPgDatabase


def test_state_forwards() -> None:
    operation = CreateModel(
        "User",
        {
            "name": pw.CharField(max_length=100),
            "email": pw.CharField(max_length=255, null=True),
        },
        {},
    )
    state = State()
    operation.state_forwards(state)
    model = state["user"]

    assert model.__name__ == "User"
    assert isinstance(model.email, pw.CharField)
    assert isinstance(model.name, pw.CharField)


def test_database_forwards(patched_pg_db: PatchedPgDatabase) -> None:
    operation = CreateModel(
        "User",
        {
            "check_char_length": pw.CharField(max_length=50),
            "check_null": pw.CharField(null=True, index=True),
            "column_different": pw.IntegerField(column_name="other_column_name"),
            "check_decimal": pw.DecimalField(max_digits=3, decimal_places=4),
            "check_default_constraint": pw.DateField(constraints=[pw.SQL("DEFAULT now()")]),
        },
        {"table_name": "some_name"},
    )
    to_state = State()
    operation.state_forwards(to_state)

    operation.database_forwards(SchemaMigrator.from_database(patched_pg_db), State(), to_state)[0]()

    assert patched_pg_db.queries == [
        'CREATE TABLE "some_name" ("id" SERIAL NOT NULL PRIMARY KEY, '
        '"check_char_length" VARCHAR(50) NOT NULL, '
        '"check_null" VARCHAR(255), '
        '"other_column_name" INTEGER NOT NULL, '
        '"check_decimal" NUMERIC(3, 4) NOT NULL, '
        '"check_default_constraint" DATE NOT NULL DEFAULT now())',
        'CREATE INDEX "some_name_check_null" ON "some_name" ("check_null")',
    ]
