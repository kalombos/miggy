import pathlib
from textwrap import dedent

import peewee as pw

try:
    from playhouse.postgres_ext import Psycopg3Database
except ImportError:  # peewee == 3.17.9
    Psycopg3Database = None

from miggy.router import Router


def test_router_build_state_from_migrations(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.create_model("tag", fields={"tag": pw.CharField()})
            """
        )
    )
    router = Router(db, migrate_dir=mig_dir)
    router.model.create(name="001_create")

    router.build_state_from_migrations()

    assert "tag" in router.state


def test_router_run_one__only_state(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.create_model("tag", fields={"tag": pw.CharField()})
            """
        )
    )
    router = Router(db, migrate_dir=mig_dir)

    router.run_one("001_create", change_schema=False, change_history=False)

    assert "tag" in router.state
    assert not db.table_exists("tag")


def test_router_run_one(tmp_path: pathlib.Path) -> None:
    db = pw.SqliteDatabase(":memory:")
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_create.py").write_text(
        dedent(
            """
            import peewee as pw


            def migrate(migrator, database, fake=False):
                migrator.create_model("tag", fields={"tag": pw.CharField()})


            def rollback(migrator, database, fake=False):
                migrator.remove_model("tag")
            """
        )
    )
    name = "001_create"
    router = Router(db, migrate_dir=mig_dir)

    router.run_one(name, change_schema=True, change_history=True)

    assert "tag" in router.state
    assert db.table_exists("tag")

    router.run_one(name, change_schema=True, change_history=True, backward=True)
    assert "tag" not in router.state
    assert not db.table_exists("tag")
