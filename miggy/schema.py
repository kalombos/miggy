from collections.abc import Callable
from typing import Any

import peewee as pw
from playhouse.migrate import MySQLDatabase, Operation, PostgresqlDatabase, SqliteDatabase, operation
from playhouse.migrate import MySQLMigrator as MqM
from playhouse.migrate import PostgresqlMigrator as PgM
from playhouse.migrate import SchemaMigrator as ScM
from playhouse.migrate import SqliteMigrator as SqM
from playhouse.postgres_ext import ArrayField

from miggy.deconstructor import ForeignKeyFieldDeconstructor
from miggy.types import ModelCls
from miggy.utils import (
    ModelIndex,
    array_field,
    extract_check_meta,
    get_default_constraint_value,
    get_single_index,
    get_single_index_name,
    has_single_index,
    make_single_index,
)


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
    def drop_primary_key_constraint(self, table: str, column_name: str):
        raise NotImplementedError

    @operation
    def add_primary_key_constraint(self, table: str, column_name: str):
        raise NotImplementedError

    def _types_not_equal(self, old_field: pw.Field, new_field: pw.Field) -> bool:
        # corner case for array field
        if isinstance(old_field, ArrayField) and isinstance(new_field, ArrayField):
            if old_field.dimensions != new_field.dimensions:
                return True
            if array_field(old_field).get_modifiers() != array_field(new_field).get_modifiers():
                return True
        return old_field.field_type != new_field.field_type or old_field.get_modifiers() != new_field.get_modifiers()

    @operation
    def _resolve_alter_column_type(self, old_field: pw.Field, new_field: pw.Field):
        if self._types_not_equal(old_field, new_field):
            table_name = new_field.model._meta.table_name
            return self.alter_column_type(table_name, new_field.column_name, new_field)
        return []

    @operation
    def _resolve_alter_default_constraint(self, old_field: pw.Field, new_field: pw.Field):
        old_value = get_default_constraint_value(old_field)
        new_value = get_default_constraint_value(new_field)
        table_name = old_field.model._meta.table_name
        if old_value != new_value:
            if new_value:
                return [self.add_column_default(table_name, new_field.column_name, new_value)]
            else:
                return [
                    self.drop_column_default(
                        table_name,
                        new_field.column_name,
                    )
                ]
        return []

    @operation
    def _resolve_alter_check_constraints(self, old_field: pw.Field, new_field: pw.Field):
        old_constraints = set(extract_check_meta(old_field))
        new_constraints = set(extract_check_meta(new_field))
        table_name = new_field.model._meta.table_name

        ops = []
        for constraint in sorted(old_constraints - new_constraints):
            ops.append(self.drop_constraint(table_name, constraint.name))

        for constraint in sorted(new_constraints - old_constraints):
            ops.append(self.add_check_constraint(table_name, constraint.name, constraint.constraint))
        return ops

    @operation
    def add_check_constraint(self, table_name: str, name: str, constraint: str):
        return self.add_constraint(table_name, name, pw.SQL("CHECK (%s)" % constraint))

    @operation
    def _resolve_alter_primary_key(self, old_field: pw.Field, new_field: pw.Field):
        table_name = new_field.model._meta.table_name
        if not old_field.primary_key and new_field.primary_key:
            return self.add_primary_key_constraint(table_name, new_field.column_name)
        elif old_field.primary_key and not new_field.primary_key:
            return self.drop_primary_key_constraint(table_name)
        return []

    @operation
    def _resolve_alter_indexes(self, old_field: pw.Field, new_field: pw.Field):
        if new_field.unique and old_field.unique:
            return []
        if not new_field.unique and not old_field.unique and new_field.index == old_field.index:
            return []
        table_name = old_field.model._meta.table_name
        _ops: list[Operation] = []
        if has_single_index(old_field):
            # We have already renamed the column so create name from the new field
            _ops.append(self.drop_index(table_name, get_single_index_name(new_field)))
        if model_index := get_single_index(new_field):
            _ops.append(self.add_model_index(model_index))
        return _ops

    @operation
    def _resolve_alter_fk_constraint(self, old_field: pw.Field, new_field: pw.Field) -> list[Operation]:
        _ops: list[Operation] = []
        is_old_field_fk = isinstance(old_field, pw.ForeignKeyField)
        is_new_field_fk = isinstance(new_field, pw.ForeignKeyField)
        if (
            is_old_field_fk
            and is_new_field_fk
            and (
                ForeignKeyFieldDeconstructor(old_field).deconstruct_fk_params()
                == ForeignKeyFieldDeconstructor(new_field).deconstruct_fk_params()
            )
        ):
            # Nothing's changed for fk
            return _ops
        table_name = old_field.model._meta.table_name
        if is_old_field_fk:
            # we use new_field.column_name because we may have rename column before
            _ops.append(self.drop_foreign_key_constraint(table_name, new_field.column_name))
        if is_new_field_fk:
            _ops.append(
                self.add_foreign_key_constraint(
                    table_name,
                    new_field.column_name,
                    new_field.rel_model._meta.table_name,  # type: ignore[attr-defined]
                    new_field.rel_field.column_name,  # type: ignore[attr-defined]
                    new_field.on_delete,  # type: ignore[attr-defined]
                    new_field.on_update,  # type: ignore[attr-defined]
                    constraint_name=new_field.constraint_name,  # type: ignore[attr-defined]
                )
            )
        return _ops

    @operation
    def _resolve_alter_nullable(self, old_field: pw.Field, new_field: pw.Field):
        if old_field.null != new_field.null:
            _operation = self.drop_not_null if new_field.null else self.add_not_null
            return [_operation(old_field.model._meta.table_name, new_field.column_name)]
        return []

    @operation
    def alter_field(self, old_field: pw.Field, new_field: pw.Field):
        return [
            self.resolve_rename_field(new_field.model._meta.table_name, old_field, new_field),
            self._resolve_alter_column_type(old_field, new_field),
            self._resolve_alter_primary_key(old_field, new_field),
            self._resolve_alter_fk_constraint(old_field, new_field),
            self._resolve_alter_default_constraint(old_field, new_field),
            self._resolve_alter_check_constraints(old_field, new_field),
            self._resolve_alter_nullable(old_field, new_field),
            self._resolve_alter_indexes(old_field, new_field),
        ]

    @operation
    def select_schema(self, schema):
        """Select database schema"""
        raise NotImplementedError

    @operation
    def sql(self, sql, params: tuple[Any, ...] | None = None):
        """Execute raw SQL."""
        return pw.SQL(sql, params)

    @operation
    def add_field(self, field: pw.Field) -> list:
        # Adding a column is complicated by the fact that if there are rows
        # present and the field is non-null, then we need to first add the
        # column as a nullable field, then set the value, then add a not null
        # constraint.
        column_name = field.column_name
        table = field.model._meta.table_name

        default_required = all(
            (
                get_default_constraint_value(field) is None,
                not field.auto_increment,
                field.sequence is None,
                not field.null,
            )
        )
        if default_required and field.default is None:
            raise ValueError(
                "%s is not null, not a sequence, and not a primary key, but has no default value" % column_name
            )

        is_foreign_key = isinstance(field, pw.ForeignKeyField)
        if is_foreign_key and not field.rel_field:  # type: ignore[attr-defined]
            raise ValueError("Foreign keys must specify a `field`.")

        operations = [self.alter_add_column(table, column_name, field)]

        if not field.null:
            if default_required:
                operations.append(
                    self.apply_default(table, column_name, field),
                )

            operations.append(self.add_not_null(table, column_name))

        if is_foreign_key and self.explicit_create_foreign_key:
            operations.append(
                self.add_foreign_key_constraint(
                    table,
                    column_name,
                    field.rel_model._meta.table_name,  # type: ignore[attr-defined]
                    field.rel_field.column_name,  # type: ignore[attr-defined]
                    field.on_delete,  # type: ignore[attr-defined]
                    field.on_update,  # type: ignore[attr-defined]
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
            operations.append(self.rename_index(old_model_index._name, new_single_index._name))  # type: ignore[attr-defined]
        return operations

    @operation
    def resolve_rename_field(self, table: str, old_field: pw.Field, new_field: pw.Field):
        if old_field.column_name != new_field.column_name:
            operations = [self.rename_column(table, old_field.column_name, new_field.column_name)]
            operations.append(self.resolve_single_index_name(old_field, new_field))
            return operations
        return []

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

    def get_primary_key_constraint(self, table: str) -> str:
        sql = """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = %s::regclass
            AND contype = 'p';
        """
        cursor = self.database.execute_sql(sql, (table,))
        return cursor.fetchall()[0][0]

    @operation
    def drop_primary_key_constraint(self, table: str):
        pk_constraint = self.get_primary_key_constraint(table)
        return self.drop_constraint(table, pk_constraint)

    @operation
    def drop_foreign_key_constraint(self, table: str, column_name: str):
        fk_constraint = self.get_foreign_key_constraint(table, column_name)
        return self.drop_constraint(table, fk_constraint)

    @operation
    def add_primary_key_constraint(self, table: str, *column_names: str):
        return (
            self._alter_table(self.make_context(), table)
            .literal(" ADD PRIMARY KEY ")
            .sql(pw.EnclosedNodeList([pw.Entity(column) for column in column_names]))
        )


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
