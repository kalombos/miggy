import pathlib
from textwrap import dedent

import peewee as pw

from miggy.router import Router


def test_integration_test_for_old_api(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.create_model("customer", fields={"name": pw.CharField()})
                migrator.create_model(
                    "order",
                    fields={
                        "number": pw.CharField(),
                        "uid": pw.CharField(unique=True),
                        "customer_id": pw.ForeignKeyField("customer", column_name="customer_id"),
                    },
                )


            def rollback(migrator, database, fake=False):
                migrator.remove_model("order")
                migrator.remove_model("customer")
            """
        )
    )
    (mig_dir / "002_evolve.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.add_fields("order", finished=pw.BooleanField(default=False))
                migrator.remove_fields("order", "finished", "uid", "customer_id")
                migrator.add_fields("order", customer=pw.ForeignKeyField("customer", null=True))
                migrator.rename_field("order", "number", "identifier")
                migrator.change_fields("order", identifier=pw.IntegerField(default=0))
                migrator.drop_not_null("order", "identifier")
                migrator.add_index("order", "identifier", "customer", name="some_name")


            def rollback(migrator, database, fake=False):
                pass
            """
        )
    )
    (mig_dir / "003_finish.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.sql('UPDATE "order" SET identifier = 77')
                migrator.drop_index("order", "some_name")
                migrator.remove_fields("order", "customer")


            def rollback(migrator, database, fake=False):
                pass
            """
        )
    )
    (mig_dir / "004_rename.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.rename_table("order", "new_name")


            def rollback(migrator, database, fake=False):
                pass
            """
        )
    )

    router = Router(db, migrate_dir=mig_dir)
    router.run_one("001_create", change_schema=True, change_history=True)
    router.run_one("002_evolve", change_schema=True, change_history=True)

    Order = router.state["order"]
    assert db.table_exists("customer")
    assert db.table_exists("order")
    assert "finished" not in Order._meta.fields
    assert "identifier" in Order._meta.fields
    assert "number" not in Order._meta.fields
    assert "customer" in Order._meta.fields
    assert Order._meta.fields["identifier"].null is True
    assert Order.identifier.field_type == "INT"
    assert "some_name" in Order._meta.indexes_state
    Order.create(identifier=55)
    assert Order.get().identifier == 55

    router.run_one("003_finish", change_schema=True, change_history=True)

    assert Order.get().identifier == 77
    assert "customer" not in Order._meta.fields
    assert "some_name" not in Order._meta.indexes_state

    router.run_one("004_rename", change_schema=True, change_history=True)

    assert Order._meta.table_name == "new_name"
    assert not db.table_exists("order")
    assert db.table_exists("new_name")
    assert router.done == ["001_create", "002_evolve", "003_finish", "004_rename"]
    assert [c.name for c in db.get_columns("new_name")] == ["id", "identifier"]


def test_router_read_extracts_operations(tmp_path: pathlib.Path) -> None:
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_test.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.create_model("tag", fields={"tag": pw.CharField()})
                if not fake:
                    migrator.sql("SELECT 1")


            def rollback(migrator, database, fake=False):
                migrator.remove_model("tag")
            """
        )
    )
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=mig_dir)

    migration = router.read("001_test", fake=True)
    assert [type(op).__name__ for op in migration.migrate] == ["CreateModel"]
    assert [type(op).__name__ for op in migration.rollback] == ["RemoveModel"]
    assert migration.atomic is True

    migration = router.read("001_test", fake=False)
    assert [type(op).__name__ for op in migration.migrate] == ["CreateModel", "RunSql"]


def test_router_read__no_operations(tmp_path: pathlib.Path) -> None:
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_test.py").write_text("")
    router = Router(pw.SqliteDatabase(":memory:"), migrate_dir=mig_dir)

    migration = router.read("001_test", fake=True)

    assert migration.migrate == []
    assert migration.rollback == []
