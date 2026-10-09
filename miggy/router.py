import os
import pkgutil
import re
import sys
import typing
from functools import cached_property
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import peewee as pw
from playhouse.db_url import connect

from miggy import LOGGER, MigrateHistory
from miggy.auto import MigrationAutodetector
from miggy.compat.migrator import Migrator
from miggy.operations import MigrateOperation, Migration
from miggy.schema import SchemaMigrator
from miggy.state import State
from miggy.utils import MIGRATION_TEMPLATE, deprecated_warn, exec_in
from miggy.writer import MigrationAttrWriter, OperationWriter


class MigrationError(Exception):
    pass


class FakeInitialError(MigrationError):
    pass


DEFAULT_MIGRATE_DIR = "migrations"
UNDEFINED = object()
VOID = lambda migrator, database, fake: None  # noqa


def add_to_sys_path(directory: str | Path) -> None:
    if directory not in sys.path:
        sys.path.insert(0, str(directory))


class Router(object):
    """Abstract base class for router."""

    filemask = re.compile(r"[\d]{3}_[^\.]+\.py$")

    def __init__(
        self,
        database: str | pw.Database | pw.Proxy | None,
        migrate_table: str = "migratehistory",
        migrate_dir: str | Path = "migrations",
        ignore: list[str] | None = None,
        schema: str | None = None,
        working_dir: str | Path | None = None,
    ) -> None:
        if isinstance(database, str):
            database = connect(database)
        if not isinstance(database, (pw.Database, pw.Proxy)):
            raise RuntimeError("Invalid database: %s" % database)
        if isinstance(database, pw.Proxy):
            # Legacy
            database = database.obj
        self.database = cast("pw.Database", database)
        self.schema_migrator = SchemaMigrator.from_database(self.database)
        working_dir = working_dir or os.getcwd()
        self.working_dir = Path(working_dir)
        # Need to append the working_dir to the path for import to work.
        add_to_sys_path(self.working_dir)
        self.migrate_dir = self.working_dir / migrate_dir
        self.migrate_table = migrate_table
        self.schema = schema
        self.ignore = ignore or []
        self.migration_template = MIGRATION_TEMPLATE.read_text()
        self.state = State()

    def build_state_from_migrations(self, use_unapplied: bool = False) -> None:
        migrations = self.todo if use_unapplied else self.done
        for name in migrations:
            self.run_one(name)

    @cached_property
    def model(self) -> typing.Type[MigrateHistory]:
        """Initialize and cache MigrationHistory model."""
        MigrateHistory._meta.database = self.database
        MigrateHistory._meta.table_name = self.migrate_table
        MigrateHistory._meta.schema = self.schema
        MigrateHistory.create_table(True)
        return MigrateHistory

    @property
    def todo(self):
        """Scan migrations in file system."""
        if not os.path.exists(self.migrate_dir):
            LOGGER.warning("Migration directory: %s does not exist.", self.migrate_dir)
            os.makedirs(self.migrate_dir)
        return sorted(f[:-3] for f in os.listdir(self.migrate_dir) if self.filemask.match(f))

    @property
    def done(self):
        """Scan migrations in database."""
        return [mm.name for mm in self.model.select().order_by(self.model.id)]

    @property
    def diff(self):
        """Calculate difference between fs and db."""
        done = set(self.done)
        return [name for name in self.todo if name not in done]

    def load_project_state(self, auto) -> State:
        modules = [auto]
        if isinstance(auto, bool):
            modules = [m for _, m, ispkg in pkgutil.iter_modules([str(self.working_dir)]) if ispkg]

        models = [m for module in modules for m in load_models(module)]

        return State({m._meta.name: m for m in models if m._meta.name not in self.ignore})

    def create(self, name="auto", auto=False, fake_initial: bool = False) -> str | None:
        """Create a migration.
        :param auto: Python module path to scan for models.
        """
        forward_changes = []
        backward_changes = []
        if auto:
            try:
                project_state = self.load_project_state(auto)
            except ImportError:
                LOGGER.exception("Can't import models module")
                return None

            self.build_state_from_migrations(use_unapplied=True)

            forward_changes = detect_changes(self.state, project_state)
            if not forward_changes:
                LOGGER.warning("No changes found.")
                return None

            backward_changes = detect_changes(project_state, self.state)

        LOGGER.info('Creating migration "%s"', name)
        name = self.compile(name, forward_changes, backward_changes, fake_initial=fake_initial)
        LOGGER.info('Migration has been created as "%s"', name)
        return name

    def _serialize_changes(self, changes: list[MigrateOperation]):
        imports = set()
        serialized_changes = []
        for c in changes:
            writer = OperationWriter(c)
            serialized_changes.append(writer.serialize())
            imports.update(writer.imports)

        return "\n".join(serialized_changes), imports

    def _compile_template(
        self,
        name: str,
        forward_changes: list[MigrateOperation],
        backward_changes: list[MigrateOperation],
        attrs: str,
    ) -> str:
        forward, imports = self._serialize_changes(forward_changes)
        backward, backward_imports = self._serialize_changes(backward_changes)
        imports.update(backward_imports)

        return self.migration_template.format(
            forward=forward, backward=backward, name=name, imports="\n".join(imports), attrs=attrs
        )

    def compile(
        self,
        name,
        forward_changes: list[MigrateOperation],
        backward_changes: list[MigrateOperation],
        num=None,
        fake_initial: bool = False,
    ) -> str:
        """Create a migration."""

        if num is None:
            num = len(self.todo) + 1

        attrs = {"atomic": True}
        if fake_initial:
            attrs["fake_initial"] = True

        name = f"{num:03}_{name}"
        if fake_initial and num != 1:
            raise FakeInitialError(f'fake_initial=True is only supported for migration "001", got "{name}".')
        filename = f"{name}.py"
        path = os.path.join(self.migrate_dir, filename)
        template = self._compile_template(
            filename,
            forward_changes=forward_changes,
            backward_changes=backward_changes,
            attrs=MigrationAttrWriter(attrs).serialize(),
        )
        with open(path, "w") as f:
            f.write(template)

        return name

    def read(self, name, fake: bool) -> Migration:
        """Read migration from file."""
        call_params: dict[str, str] = {}
        if os.name == "nt" and sys.version_info >= (3, 0):
            # if system is windows - force utf-8 encoding
            call_params["encoding"] = "utf-8"
        with open(os.path.join(self.migrate_dir, name + ".py"), **call_params) as f:  # type: ignore[call-overload]
            code = f.read()

        scope: dict[str, Any] = {}
        exec_in(code, scope)

        migration_cls = scope.get("Migration", None)

        if migration_cls is None:
            migration_cls = self.create_migration_from_legacy_format(scope, fake)

        return migration_cls(name, self.schema_migrator, self.model)

    def create_migration_from_legacy_format(self, scope: dict[str, Any], fake: bool) -> type[Migration]:
        atomic, migrate, rollback = (
            scope.get("__ATOMIC", True),
            scope.get("migrate", VOID),
            scope.get("rollback", VOID),
        )

        def extract_operations(f) -> list[MigrateOperation]:
            m = Migrator()
            f(m, self.database, fake=fake)
            _operations = m.operations[:]
            m.operations = []
            return _operations

        class _Migration(Migration):
            pass

        _Migration.atomic = atomic
        _Migration.forward = extract_operations(migrate)
        _Migration.backward = extract_operations(rollback)
        return _Migration

    def resolve_schema(self) -> None:
        if self.schema:
            self.database.execute_sql("SET search_path TO %s", (self.schema,))

    def run_one(
        self,
        name: str,
        change_schema: bool = False,
        change_history: bool = False,
        backward: bool = False,
    ) -> None:
        """Run/emulate a migration with given name."""
        try:
            migration = self.read(name, not change_schema)
            LOGGER.info('%s "%s"', "Rolling back" if backward else "Migrate", name)
            self.resolve_schema()
            migration.apply(self.state, change_schema, change_history, backward)
        except Exception:
            operation = "Migration" if not backward else "Rollback"
            LOGGER.exception("%s failed: %s", operation, name)
            raise

    def run(self, name=None, fake=False):
        """Run migrations."""
        LOGGER.info("Starting migrations")

        done = []
        diff = self.diff
        if not diff:
            LOGGER.info("There is nothing to migrate")
            return done

        self.build_state_from_migrations()
        for mname in diff:
            self.run_one(mname, change_schema=not fake, change_history=True)
            done.append(mname)
            if name and name == mname:
                break

        return done

    def rollback(self, name):
        name = name.strip()
        done = self.done
        if not done:
            raise MigrationError("No migrations are found.")
        if name != done[-1]:
            raise MigrationError("Only last migration can be canceled.")

        self.build_state_from_migrations()
        self.run_one(name, change_schema=True, backward=True, change_history=True)
        LOGGER.warning("Downgraded migration: %s", name)

    # Candidates for deprecation

    def merge(self, name="initial"):
        """Merge migrations into one."""
        self.build_state_from_migrations()
        migrate_changes = detect_changes(State(), self.state)
        if not migrate_changes:
            return LOGGER.error("Can't merge migrations")

        self.clear()

        LOGGER.info('Merge migrations into "%s"', name)
        rollback_changes = detect_changes(self.state, State())
        name = self.compile(name, migrate_changes, rollback_changes, num=1)

        self.state = State()
        self.run_one(name, change_schema=False, change_history=True)
        LOGGER.info('Migrations has been merged into "%s"', name)

    def clear(self):
        """Clear migrations."""
        self.model.delete().execute()

        # Remove migrations from fs
        for name in self.todo:
            filename = os.path.join(self.migrate_dir, name + ".py")
            os.remove(filename)


def load_models(module):
    """Load models from given module."""
    modules = _import_submodules(module)
    return {m for module in modules for m in filter(_check_model, (getattr(module, name) for name in dir(module)))}


def _import_submodules(package, passed=UNDEFINED):
    if passed is UNDEFINED:
        passed = set()

    if isinstance(package, str):
        package = import_module(package)

    modules = []

    for _loader, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        if name in passed:
            continue
        passed.add(name)

        module = sys.modules.get(name)
        if module is None:
            module = import_module(name)

        modules.append(module)
        if is_pkg:
            modules += _import_submodules(module, passed=passed)

    return modules


def _check_model(obj, models=None):
    """Checks object if it's a peewee model and unique."""
    return isinstance(obj, type) and issubclass(obj, pw.Model) and hasattr(obj, "_meta")


def detect_changes(
    from_state: State,
    to_state: State,
) -> list[MigrateOperation]:
    return MigrationAutodetector(from_state, to_state).changes()


def get_router(directory, database, schema=None, verbose=0, conf_path: Path | None = None) -> Router:
    VERBOSE = ["WARNING", "INFO", "DEBUG", "NOTSET"]
    logging_level = VERBOSE[verbose]
    config: dict[str, Any] = {}
    migrate_table = "migratehistory"
    working_directory = os.getcwd()
    migrate_dir = directory
    ignore = None

    if conf_path:
        working_directory = conf_path.parent.as_posix()
    else:
        deprecated_warn("Calling get_router() with conf_path=None is deprecated. Please provide a conf_path.")
        conf_path = Path(directory) / "conf.py"

    if conf_path.exists():
        # for imports in config
        add_to_sys_path(working_directory)
        with open(conf_path) as cfg:
            exec_in(cfg.read(), config, config)
            database = config.get("DATABASE", database)
            ignore = config.get("IGNORE", ignore)
            schema = config.get("SCHEMA", schema)
            migrate_table = config.get("MIGRATE_TABLE", migrate_table)
            migrate_dir = config.get("MIGRATE_DIR", migrate_dir)
            logging_level = config.get("LOGGING_LEVEL", logging_level).upper()

    LOGGER.setLevel(logging_level)

    try:
        return Router(
            database,
            migrate_table=migrate_table,
            migrate_dir=migrate_dir,
            ignore=ignore,
            schema=schema,
            working_dir=working_directory,
        )
    except RuntimeError as exc:
        LOGGER.error(exc)
        return sys.exit(1)
