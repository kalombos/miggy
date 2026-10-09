import os
import pathlib
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from miggy.cli import _load_router, cli
from miggy.router import Router
from miggy.utils import CONFIG_TEMPLATE

runner = CliRunner()


@pytest.fixture
def dir_option(tmpdir):
    return "--directory=%s" % tmpdir


@pytest.fixture
def default_config(tmp_path: Path) -> None:
    conf = tmp_path / "miggyconf.py"
    conf.write_text("DATABASE = 'sqlite:///:memory:'\nMIGRATE_DIR = 'custom_migrations'")
    os.mkdir(tmp_path / "custom_migrations")
    return conf


@pytest.fixture
def db_url(tmpdir):
    db_path = "%s/test_sqlite.db" % tmpdir
    open(db_path, "a").close()
    return "sqlite:///%s" % db_path


@pytest.fixture
def db_option(db_url):
    return "--database=%s" % db_url


@pytest.fixture
def router(tmpdir, db_url):
    return lambda: Router(database=db_url, migrate_dir=str(tmpdir))


@pytest.fixture
def migrations(router):
    migrations_number = 5
    name = "test"
    for _ in range(migrations_number):
        router().create(name)
    return ["00%s_test" % i for i in range(1, migrations_number + 1)]


@pytest.fixture
def migrations_str(migrations):
    return ", ".join(migrations)


def _click_context(conf_path: Path) -> click.Context:
    ctx = click.Context(cli)
    ctx.meta["config_path"] = conf_path
    return ctx


def test_help() -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "makemigrations" in result.output
    assert "migrate" in result.output
    assert "rollback" in result.output
    assert "list" in result.output


def test_load_router(default_config: Path) -> None:

    with _click_context(default_config):
        router = _load_router("migrations", "sqlite:///:memory:")

    assert router.working_dir == default_config.parent
    assert router.migrate_dir == default_config.parent / "custom_migrations"


def test_load_router_missing_config(capsys: pytest.CaptureFixture[str]) -> None:
    conf = pathlib.Path("miggyconf.py")

    with _click_context(conf):
        router = _load_router("migrations", "sqlite:///:memory:")

    assert f"{conf} is not found" in capsys.readouterr().out
    assert router.migrate_dir == pathlib.Path(os.getcwd()) / "migrations"


def test_init_default_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["init"])

    assert result.exit_code == 0
    assert (tmp_path / "miggyconf.py").exists()


def test_init_creates_config(tmp_path: Path) -> None:
    runner = CliRunner()

    config_path = tmp_path / "config" / "config.py"

    result = runner.invoke(
        cli,
        ["--config", str(config_path), "init"],
    )

    assert result.exit_code == 0
    assert config_path.exists()
    assert config_path.read_text() == CONFIG_TEMPLATE.read_text()
    assert f"Created {config_path}" in result.output


def test_init_does_not_overwrite_existing_config(default_config: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["--config", str(default_config), "init"],
    )

    assert result.exit_code == 1
    assert "already exists" in result.output
    assert default_config.read_text() == "DATABASE = 'sqlite:///:memory:'\nMIGRATE_DIR = 'custom_migrations'"


def test_makemigrations__autosource(dir_option, db_option):
    result = runner.invoke(
        cli, ["makemigrations", dir_option, db_option, "--auto-source", "tests.test_autodiscover.some_folder_one"]
    )
    assert "Migration created: 001_auto_" in result.output


def test_makemigrations_fake_initial(default_config: Path) -> None:
    migration_dir = default_config.parent / "custom_migrations"
    result = runner.invoke(
        cli,
        [
            "--config",
            str(default_config),
            "makemigrations",
            "--fake-initial",
            "--auto-source",
            "tests.test_autodiscover.some_folder_one",
        ],
    )
    assert result.exit_code == 0
    assert "Migration created: 001_auto_" in result.output

    migration_file = next(Path(migration_dir).glob("001_auto_*.py"))
    assert "fake_initial = True" in migration_file.read_text()


def test_makemigrations_fake_initial_not_first_migration(default_config: Path) -> None:
    runner.invoke(
        cli,
        [
            "--config",
            str(default_config),
            "makemigrations",
            "--empty",
        ],
    )
    result = runner.invoke(
        cli,
        ["--config", str(default_config), "makemigrations", "--fake-initial", "--empty"],
    )
    assert result.exit_code == 1
    assert "The --fake-initial option can only be used with the first migration." in result.output


def test_migrate(dir_option, db_option, migrations_str):
    result = runner.invoke(cli, ["migrate", dir_option, db_option])
    assert result.exit_code == 0
    assert "Migrations completed: %s" % migrations_str in result.output


def test_fake(dir_option, db_option, migrations_str, router):
    result = runner.invoke(cli, ["migrate", dir_option, db_option, "-v", "--fake"])
    assert result.exit_code == 0
    assert "Migrations completed: %s" % migrations_str in result.output

    # TODO: Find a way of testing fake. This is unclear why the following fails.
    # assert not router().done


def test_rollback(dir_option, db_option, router, migrations):
    router().run()

    count_overflow = len(migrations) + 1
    result = runner.invoke(cli, ["rollback", dir_option, db_option, "--count=%s" % count_overflow])
    assert result.exception
    assert "Unable to rollback %s migrations" % count_overflow in result.exception.args[0]
    assert router().done == migrations

    result = runner.invoke(cli, ["rollback", dir_option, db_option])
    assert not result.exception
    assert router().done == migrations[:-1]

    result = runner.invoke(cli, ["rollback", dir_option, db_option, "004_test"])
    assert not result.exception
    assert router().done == migrations[:-2]

    result = runner.invoke(cli, ["rollback", dir_option, db_option, "--count=2"])
    assert not result.exception
    assert router().done == migrations[:-4]

    result = runner.invoke(cli, ["rollback", dir_option, db_option, "005_test"])
    assert result.exception
    assert result.exception.args[0] == "Only last migration can be canceled."
    assert router().done == migrations[:-4]


def test_list(dir_option, db_option, migrations):
    result = runner.invoke(cli, ["list", dir_option, db_option])
    assert "Migrations are done:\n" in result.output
    assert "Migrations are undone:\n%s" % "\n".join(migrations) in result.output


# Candidates for deprecation


def test_create(dir_option, db_option):
    for _ in range(2):
        result = runner.invoke(cli, ["create", dir_option, db_option, "-vvv", "test"])
        assert result.exit_code == 0
