from collections.abc import Callable
from typing import Any

import peewee as pw
from playhouse.migrate import MySQLDatabase, PostgresqlDatabase, SqliteDatabase, operation
from playhouse.migrate import MySQLMigrator as MqM
from playhouse.migrate import PostgresqlMigrator as PgM
from playhouse.migrate import SchemaMigrator as ScM
from playhouse.migrate import SqliteMigrator as SqM

from miggy.types import ModelCls
from miggy.utils import ModelIndex, get_default_constraint, get_single_index, make_single_index


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

    @operation
    def _resolve_alter_column_type(self, old_field: pw.Field, new_field: pw.Field):
        if old_field.field_type != new_field.field_type or old_field.get_modifiers() != new_field.get_modifiers():
            table_name = new_field.model._meta.table_name
            return self.alter_column_type(table_name, new_field.column_name, new_field)
        return []

    @operation
    def _resolve_alter_primary_key(self, old_field: pw.Field, new_field: pw.Field):
        table_name = new_field.model._meta.table_name
        if not old_field.primary_key and new_field.primary_key:
            return self.add_primary_key_constraint(table_name, new_field.column_name)
        elif old_field.primary_key and not new_field.primary_key:
            return self.drop_primary_key_constraint(table_name)
        return []

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
            (get_default_constraint(field) is None, not field.auto_increment, field.sequence is None, not field.null)
        )
        if default_required and field.default is None:
            raise ValueError(
                "%s is not null, not a sequence, and not a primary key, but has no default value" % column_name
            )

        is_foreign_key = isinstance(field, pw.ForeignKeyField)
        if is_foreign_key and not field.rel_field:
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
