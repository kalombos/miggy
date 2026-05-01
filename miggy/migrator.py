from collections.abc import Callable
from typing import Any

import peewee as pw
from playhouse.migrate import (
    SQL,
    MySQLDatabase,
    Operation,
    PostgresqlDatabase,
    SqliteDatabase,
    operation,
)
from playhouse.migrate import MySQLMigrator as MqM
from playhouse.migrate import PostgresqlMigrator as PgM
from playhouse.migrate import SchemaMigrator as ScM
from playhouse.migrate import SqliteMigrator as SqM

from miggy import LOGGER
from miggy.operations import (
    AddFields,
    AddIndex,
    ChangeFields,
    ChangeNullable,
    CreateModel,
    DropIndex,
    MigrateOperation,
    RemoveFields,
    RemoveModel,
    RenameField,
    RenameTable,
    RunPython,
    RunPythonF,
    RunSql,
)
from miggy.state import State
from miggy.types import ModelCls
from miggy.utils import (
    ModelIndex,
    get_default_constraint,
    get_single_index,
    make_single_index,
)


class Migration:
    def __init__(self, state: State, schema_migrator: "SchemaMigrator", schema: str | None = None) -> None:
        self.state = state
        self.schema_migrator = schema_migrator
        self.schema = schema
        self.operations: list[Operation | Callable] = []

    def append(self, op: MigrateOperation) -> None:
        self.state.create_snapshot()
        op.state_forwards(self.state)
        from_state = self.state.pop_snapshot()
        self.operations.extend(op.database_forwards(self.schema_migrator, from_state, self.state))

    def apply(self, change_schema: bool) -> None:
        if not change_schema:
            return

        if self.schema:
            _ops = [self.schema_migrator.select_schema(self.schema), *self.operations]
        else:
            _ops = [*self.operations]

        for op in _ops:
            if isinstance(op, Operation):
                LOGGER.info("%s %s", op.method, op.args)
                op.run()
            else:
                op()

    def clean(self) -> None:
        self.operations = []


class SchemaMigrator(ScM):
    """Extended **playhouse.migrate.SchemaMigrator** from **peewee**"""

    @classmethod
    def from_database(cls, database):
        """Initialize migrator by db."""
        if isinstance(database, PostgresqlDatabase):
            return PostgresqlMigrator(database)
        if isinstance(database, SqliteDatabase):
            return SqliteMigrator(database)
        if isinstance(database, MySQLDatabase):
            return MySQLMigrator(database)
        return super(SchemaMigrator, cls).from_database(database)

    @operation
    def select_schema(self, schema):
        """Select database schema"""
        raise NotImplementedError()

    @operation
    def sql(self, sql, params: tuple[Any, ...] | None = None):
        """Execute raw SQL."""
        return SQL(sql, params)

    @operation
    def add_column(self, table, column_name, field):
        # Adding a column is complicated by the fact that if there are rows
        # present and the field is non-null, then we need to first add the
        # column as a nullable field, then set the value, then add a not null
        # constraint.
        default_constraint = get_default_constraint(field)
        if not field.null and field.default is None and not default_constraint:
            raise ValueError("%s is not null but has no default" % column_name)

        is_foreign_key = isinstance(field, pw.ForeignKeyField)
        if is_foreign_key and not field.rel_field:
            raise ValueError("Foreign keys must specify a `field`.")

        operations = [self.alter_add_column(table, column_name, field)]

        # In the event the field is *not* nullable and has no default constraint, update with the default
        # value and set not null.
        if not field.null:
            if not default_constraint:
                operations.append(
                    self.apply_default(table, column_name, field),
                )

            operations.append(self.add_not_null(table, column_name))

        if is_foreign_key and self.explicit_create_foreign_key:
            operations.append(
                self.add_foreign_key_constraint(
                    table,
                    column_name,
                    field.rel_model._meta.table_name,
                    field.rel_field.column_name,
                    field.on_delete,
                    field.on_update,
                )
            )

        if model_index := get_single_index(field):
            operations.append(self.add_model_index(model_index))
        return operations

    @operation
    def add_model_index(self, model_index: ModelIndex):
        ctx = self.make_context()
        return ctx.sql(model_index)

    @operation
    def rename_index(self, old_name: str, new_name: str):
        """Change index name"""
        ctx = self.make_context()
        return ctx.literal("ALTER INDEX ").sql(pw.Entity(old_name)).literal(" RENAME TO ").sql(pw.Entity(new_name))

    @operation
    def resolve_single_index_name(self, old_field: pw.Field, new_field: pw.Field):
        operations = []
        if old_model_index := get_single_index(old_field):
            new_single_index = make_single_index(new_field)
            operations.append(self.rename_index(old_model_index._name, new_single_index._name))
        return operations

    @operation
    def rename_field(self, table: str, old_field: pw.Field, new_field: pw.Field):
        operations = [self.rename_column(table, old_field.column_name, new_field.column_name)]
        operations.append(self.resolve_single_index_name(old_field, new_field))
        return operations

    def create_table(self, model: ModelCls, safe: bool = False) -> Callable:
        """
        Create table from model class
        """
        model._meta.database = self.database
        model._meta.legacy_table_names = False
        return lambda: model.create_table(safe=safe)

    def drop_table(self, model: ModelCls, safe: bool = False) -> Callable:
        """
        Drop model table
        """
        model._meta.database = self.database
        return lambda: model.drop_table(safe=safe)


class MySQLMigrator(SchemaMigrator, MqM):
    def alter_change_column(self, table, column, field):
        """Support change columns."""
        ctx = self.make_context()
        field_null, field.null = field.null, True
        ctx = self._alter_table(ctx, table).literal(" MODIFY COLUMN ").sql(field.ddl(ctx))
        field.null = field_null
        return ctx


class PostgresqlMigrator(SchemaMigrator, PgM):
    """Support the migrations in postgresql."""

    @operation
    def select_schema(self, schema):
        """Select database schema"""
        return self.set_search_path(schema)

    def get_foreign_key_constraint(self, table: str, column_name: str) -> str:
        sql = """
            SELECT DISTINCT
                kcu.constraint_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON (tc.constraint_name = kcu.constraint_name AND
                    tc.constraint_schema = kcu.constraint_schema AND
                    tc.table_name = kcu.table_name AND
                    tc.table_schema = kcu.table_schema)
            JOIN information_schema.constraint_column_usage AS ccu
                ON (ccu.constraint_name = tc.constraint_name AND
                    ccu.constraint_schema = tc.constraint_schema)
            WHERE
                tc.constraint_type = 'FOREIGN KEY' AND
                tc.table_name = %s AND
                tc.table_schema = current_schema() AND
                kcu.column_name  = %s"""
        cursor = self.database.execute_sql(sql, (table, column_name))
        return cursor.fetchall()[0][0]

    @operation
    def drop_foreign_key_constraint(self, table: str, column_name: str):
        fk_constraint = self.get_foreign_key_constraint(table, column_name)
        return self.drop_constraint(table, fk_constraint)


class SqliteMigrator(SchemaMigrator, SqM):
    """Support the migrations in sqlite."""

    def drop_table(self, model, cascade=True):
        """SQLite doesnt support cascade syntax by default."""
        return lambda: model.drop_table(cascade=False)

    def alter_column_type(self, table, column, field):
        """Support change columns."""
        return self._update_column(table, column, lambda a, b: b)

    def drop_column(self, table, column_name, cascade=True, legacy=True, **kwargs):
        """drop_column will not work for FK so we should use the legacy version"""
        return super(SqliteMigrator, self).drop_column(table, column_name, cascade, legacy, **kwargs)


class Migrator(object):
    """
    A class that provides shortcuts for adding migration operations.
    """

    def __init__(self, database, schema=None):
        """Initialize the migrator."""
        if isinstance(database, pw.Proxy):
            database = database.obj

        self.database = database
        self.state = State()
        self.schema_migrator = SchemaMigrator.from_database(self.database)
        self.schema = schema

        self.migration = Migration(self.state, self.schema_migrator, schema=schema)

    def add_operation(self, op: MigrateOperation) -> None:
        """
        Adds a migrate operation
        """
        self.migration.append(op)

    def run(self, change_schema: bool = True):
        self.migration.apply(change_schema)
        self.clean()

    def python(self, func: RunPythonF):
        """A shortcut for adding a :class:`RunPython` operation."""
        self.add_operation(RunPython(func))

    def sql(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        """A shortcut for adding a :class:`RunSql` operation."""
        self.add_operation(RunSql(sql, params))

    def clean(self):
        """Clean the operations."""
        self.migration.clean()

    def create_model(self, model: ModelCls) -> ModelCls:
        """A shortcut for adding a :class:`CreateModel` operation."""

        self.add_operation(CreateModel(model))
        return model

    create_table = create_model

    def remove_model(self, model_name: str) -> None:
        """A shortcut for adding a :class:`RemoveModel` operation."""

        self.add_operation(RemoveModel(model_name))

    drop_table = remove_model

    def add_fields(self, model_name: str, **fields: Any) -> None:
        """A shortcut for adding a :class:`AddFields` operation."""

        self.add_operation(AddFields(model_name, **fields))

    add_columns = add_fields

    def change_fields(self, model_name: str, **fields: pw.Field) -> None:
        """A shortcut for adding a :class:`ChangeFields` operation."""

        return self.add_operation(ChangeFields(model_name, **fields))

    change_columns = change_fields

    def remove_fields(self, model_name: str, *names: str, cascade: bool = False) -> None:
        """A shortcut for adding a :class:`RemoveFields` operation."""

        self.add_operation(RemoveFields(model_name, *names, cascade=cascade))

    drop_columns = remove_fields

    def rename_field(self, model_name: str, old_name: str, new_name: str) -> None:
        """A shortcut for adding a :class:`RenameField` operation."""

        self.add_operation(RenameField(model_name, old_name, new_name))

    rename_column = rename_field

    def rename_table(self, model_name: str, new_table_name: str) -> None:
        """A shortcut for adding a :class:`RenameTable` operation."""

        self.add_operation(RenameTable(model_name, new_table_name))

    rename_model = rename_table

    def add_index(
        self,
        model_name: str,
        *fields: str,
        name: str,
        unique: bool = False,
        where: pw.SQL | None = None,
        safe: bool = False,
        concurrently: bool = False,
    ) -> None:
        """A shortcut for adding a :class:`AddIndex` operation."""

        self.add_operation(
            AddIndex(model_name, *fields, name=name, unique=unique, where=where, safe=safe, concurrently=concurrently)
        )

    def drop_index(self, model_name: str, name: str) -> None:
        """A shortcut for adding a :class:`DropIndex` operation."""

        self.add_operation(DropIndex(model_name, name))

    def add_not_null(self, model_name: str, *names: str) -> None:
        self.add_operation(ChangeNullable(model_name, *names, is_null=False))

    def drop_not_null(self, model_name: str, *names: str) -> None:
        """Drop not null."""
        self.add_operation(ChangeNullable(model_name, *names, is_null=True))
