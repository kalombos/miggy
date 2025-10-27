from collections.abc import Callable
from functools import wraps
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

from peewee_migrate import LOGGER
from peewee_migrate.auto import fk_to_params, resolve_field
from peewee_migrate.types import ModelCls
from peewee_migrate.utils import get_default_constraint, get_default_constraint_value


class ModelIndex(pw.ModelIndex):
    def __init__(
        self, model, fields, unique=False, safe=True, where=None, using=None, name=None, concurrently=False
    ) -> None:
        self.concurrently = concurrently
        super().__init__(model=model, fields=fields, unique=unique, safe=safe, where=where, using=using, name=name)

    def __sql__(self, ctx):
        context = super().__sql__(ctx)
        if self.concurrently:
            context._sql.insert(1, "CONCURRENTLY ")
        return context


def has_single_index(field: pw.Field) -> bool:
    return field.index or field.unique


def get_single_index_name(field: pw.Field) -> str:
    return make_single_model_index(field)._name


def make_single_model_index(field: pw.Field) -> ModelIndex:
    return ModelIndex(field.model, (field,), unique=field.unique, safe=False, using=field.index_type)


def get_single_model_index(field: pw.Field) -> pw.Model:
    if has_single_index(field):
        return make_single_model_index(field)
    return None


class MigrateOperation:
    migrator: "Migrator"

    @property
    def schema_migrator(self) -> "SchemaMigrator":
        return self.migrator.schema_migrator

    def state_forwards(self) -> None:
        """
        Take the state from the previous migration, and mutate it
        so that it matches what this migration would perform.
        """

        raise NotImplementedError

    def database_forwards(self) -> list[Operation] | list[Callable]:
        """
        Perform the mutation on the database schema in the normal
        (forwards) direction.
        """
        raise NotImplementedError


class CreateModel(MigrateOperation):
    def __init__(self, model: ModelCls) -> None:
        self.model = model

    def state_forwards(self) -> None:
        # We use own attribute for indexes because we don't want to have conflict with standart index creation
        self.migrator.orm[self.model._meta.name] = self.model

    def database_forwards(self) -> list[Callable]:
        return [lambda: self.model.create_table(safe=False)]


class RemoveModel(MigrateOperation):
    def __init__(self, model: ModelCls) -> None:
        self.model = model

    def state_forwards(self) -> None:
        del self.migrator.orm[self.model._meta.name]

    def database_forwards(self) -> list[Callable]:
        return [lambda: self.model.drop_table(safe=False)]


class AddIndex(MigrateOperation):
    def __init__(
        self,
        model_cls: ModelCls,
        *fields: str,
        name: str,
        unique: bool = False,
        where: pw.SQL | None = None,
        safe: bool = False,
        concurrently: bool = False,
    ) -> None:
        self.model_index = ModelIndex(
            model=model_cls,
            fields=[resolve_field(model_cls, f) for f in fields],
            unique=unique,
            where=where,
            name=name,
            safe=safe,
            concurrently=concurrently,
        )
        self.model_cls = model_cls

    def state_forwards(self) -> None:
        self.model_cls._meta.mg_indexes[self.model_index._name] = self.model_index

    def database_forwards(self) -> list[Operation]:
        return [self.schema_migrator.add_model_index(self.model_index)]


class DropIndex(MigrateOperation):
    def __init__(self, model_cls: ModelCls, name: str) -> None:
        self.model_cls = model_cls
        self.name = name

    def state_forwards(self) -> None:
        del self.model_cls._meta.mg_indexes[self.name]

    def database_forwards(self) -> list[Operation]:
        return [self.schema_migrator.drop_index(self.model_cls._meta.table_name, self.name)]


class RenameTable(MigrateOperation):
    def __init__(self, model: ModelCls, new_table_name: str) -> None:
        self.model = model
        self.old_name = model._meta.table_name
        self.new_name = new_table_name

    def state_forwards(self) -> None:
        self.model._meta.table_name = self.new_name

    def database_forwards(self) -> list[Callable]:
        """Rename table in database."""
        return [self.schema_migrator.rename_table(self.old_name, self.new_name)]


class AddFields(MigrateOperation):
    def __init__(self, model: ModelCls, **fields: Any) -> None:
        self.model = model
        self.fields = fields

    def state_forwards(self) -> None:
        for name, field in self.fields.items():
            self.model._meta.add_field(name, field)

    def database_forwards(self) -> list[Operation]:
        ops = []
        for field in self.fields.values():
            ops.append(self.schema_migrator.add_column(self.model._meta.table_name, field.column_name, field))
        return ops


class ChangeFields(MigrateOperation):
    def __init__(self, model: ModelCls, **fields: pw.Field) -> None:
        self.model = model
        self.table_name = self.model._meta.table_name
        self.old_fields: dict[str, pw.Field] = {name: getattr(self.model, name).clone() for name in fields}
        self.fields = fields

    def state_forwards(self) -> None:
        for name, field in self.fields.items():
            self.model._meta.add_field(name, field)

    def handle_indexes(self, old_field: pw.Field, new_field: pw.Field) -> list[Operation]:
        _ops = []
        _field = new_field
        if _field.unique and old_field.unique:
            return []
        if not _field.unique and not old_field.unique and _field.index == old_field.index:
            return []

        if has_single_index(old_field):
            # We have already renamed the column so create name from the new field
            _ops.append(self.schema_migrator.drop_index(self.table_name, get_single_index_name(_field)))
        if model_index := get_single_model_index(_field):
            _ops.append(self.schema_migrator.add_model_index(model_index))
        return _ops

    def handle_fk_constraint(self, old_field: pw.Field, new_field: pw.Field) -> list[Operation]:
        _ops: list[Operation] = []
        is_old_field_fk = isinstance(old_field, pw.ForeignKeyField)
        is_new_field_fk = isinstance(new_field, pw.ForeignKeyField)
        if is_old_field_fk and is_new_field_fk and fk_to_params(old_field) == fk_to_params(new_field):
            # Nothing's changed for fk
            return _ops
        if is_old_field_fk:
            _ops.append(self.schema_migrator.drop_foreign_key_constraint(self.table_name, new_field.column_name))
        if is_new_field_fk:
            _ops.append(
                self.schema_migrator.add_foreign_key_constraint(
                    self.model._meta.table_name,
                    new_field.column_name,
                    new_field.rel_model._meta.table_name,
                    new_field.rel_field.name,
                    new_field.on_delete,
                    new_field.on_update,
                    constraint_name=new_field.constraint_name,
                )
            )
        return _ops

    def handle_default_constraint(self, old_field: pw.Field, new_field: pw.Field) -> list[Operation]:
        old_value = get_default_constraint_value(old_field) or ""
        new_value = get_default_constraint_value(new_field) or ""
        if old_value != new_value:
            if new_value:
                return [
                    self.schema_migrator.add_column_default(
                        self.model._meta.table_name, new_field.column_name, new_value
                    )
                ]
            else:
                return [
                    self.schema_migrator.drop_column_default(
                        self.model._meta.table_name,
                        new_field.column_name,
                    )
                ]
        return []

    def handle_type(self, old_field: pw.Field, new_field: pw.Field) -> list[Operation]:
        if type(old_field) is not type(new_field):
            return [
                self.schema_migrator.alter_column_type(self.model._meta.table_name, new_field.column_name, new_field)
            ]
        return []

    def database_forwards(self) -> list[Operation]:
        _ops = []
        model = self.model
        table_name = model._meta.table_name
        for name, field in self.fields.items():
            old_field = self.old_fields[name]
            old_column_name = old_field.column_name

            if old_column_name != field.column_name:
                _ops.append(self.schema_migrator.rename_field(table_name, old_field, field))

            _ops.extend(self.handle_type(old_field, field))
            _ops.extend(self.handle_fk_constraint(old_field, field))
            _ops.extend(self.handle_default_constraint(old_field, field))
            if old_field.null != field.null:
                _operation = self.schema_migrator.drop_not_null if field.null else self.schema_migrator.add_not_null
                _ops.append(_operation(table_name, field.column_name))
            _ops.extend(self.handle_indexes(old_field, field))
        return _ops


class RemoveFields(MigrateOperation):
    def __init__(self, model: ModelCls, *names: str, cascade: bool = False) -> None:
        self.model = model
        self.cascade = cascade
        self.fields = [self.model._meta.fields[name] for name in names]

    def state_forwards(self) -> None:
        for field in self.fields:
            _delete_field(self.model, field)

    def database_forwards(self) -> list[Operation]:
        """Remove fields from model."""
        ops = []
        for field in self.fields:
            ops.append(
                self.schema_migrator.drop_column(self.model._meta.table_name, field.column_name, cascade=self.cascade)
            )
        return ops


def fk_postfix(name: str) -> str:
    return name if name.endswith("_id") else name + "_id"


class RenameField(MigrateOperation):
    def __init__(self, model: ModelCls, old_name: str, new_name: str) -> None:
        self.model = model
        self.table_name = self.model._meta.table_name
        self.old_field_name = old_name
        self.new_field_name = new_name
        self.old_field = self.model._meta.fields[self.old_field_name]
        self.new_field = self.old_field.clone()
        self.new_field.column_name = self.resolve_new_name(self.old_field, new_name)

    def state_forwards(self) -> None:
        _delete_field(self.model, self.old_field)
        self.model._meta.add_field(self.new_field_name, self.new_field)

    def resolve_new_name(self, old_field: pw.Field, new_name: str) -> str:
        if isinstance(old_field, pw.ForeignKeyField):
            if old_field.column_name == fk_postfix(old_field.name):
                return fk_postfix(new_name)
        if old_field.column_name == old_field.name:
            return new_name
        return old_field.column_name

    def database_forwards(self) -> list[Operation]:
        if self.old_field.column_name != self.new_field.column_name:
            return [self.schema_migrator.rename_field(self.table_name, self.old_field, self.new_field)]
        return []


class ChangeNullable(MigrateOperation):
    def __init__(self, model: ModelCls, *names: str, is_null: bool) -> None:
        self.model = model
        self.names = names
        self.is_null = is_null

    def state_forwards(self) -> None:
        for name in self.names:
            field = self.model._meta.fields[name]
            field.null = self.is_null

    def database_forwards(self) -> list[Operation]:
        ops = []
        for name in self.names:
            field = self.model._meta.fields[name]
            _operation = self.schema_migrator.drop_not_null if self.is_null else self.schema_migrator.add_not_null
            ops.append(_operation(self.model._meta.table_name, field.column_name))
        return ops


def _delete_field(model: ModelCls, field: pw.Field) -> None:
    """Delete field from model."""
    model._meta.remove_field(field.name)
    delattr(model, field.name)
    if isinstance(field, pw.ForeignKeyField):
        delattr(model, field.object_id_name)
        delattr(field.rel_model, field.backref)


class Migration:
    def __init__(self, migrator: "Migrator") -> None:
        self.migrator = migrator
        self.ops: list[Operation | Callable] = []

    def append(self, op: MigrateOperation) -> None:
        if isinstance(op, MigrateOperation):
            op.migrator = self.migrator
            op.state_forwards()
            self.ops.extend(op.database_forwards())
        else:
            self.ops.append(op)

    def apply(self) -> None:
        for op in self.ops:
            if isinstance(op, Operation):
                LOGGER.info("%s %s", op.method, op.args)
                op.run()
            else:
                op()

    def clean(self) -> None:
        self.ops = []


class SchemaMigrator(ScM):
    """Implement migrations."""

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
    def sql(self, sql, *params):
        """Execute raw SQL."""
        return SQL(sql, *params)

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

        if model_index := get_single_model_index(field):
            operations.append(self.add_model_index(model_index))
        return operations

    @operation
    def add_model_index(self, model_index: ModelIndex):
        ctx = self.make_context()
        return ctx.sql(model_index)

    @operation
    def rename_index(self, old_name: str, new_name: str):
        ctx = self.make_context()
        return ctx.literal("ALTER INDEX ").sql(pw.Entity(old_name)).literal(" RENAME TO ").sql(pw.Entity(new_name))

    @operation
    def rename_field(self, table: str, old_field: pw.Field, new_field: pw.Field):
        operations = [self.rename_column(table, old_field.column_name, new_field.column_name)]
        if old_model_index := get_single_model_index(old_field):
            new_single_model_index = make_single_model_index(new_field)
            operations.append(self.rename_index(old_model_index._name, new_single_model_index._name))
        return operations


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


def get_model(method):
    """Convert string to model class."""

    @wraps(method)
    def wrapper(migrator, model, *args, **kwargs):
        if isinstance(model, str):
            model = migrator.orm[model.lower()]

        model._meta.database = migrator.database
        model._meta.schema = migrator.schema
        model._meta.legacy_table_names = False
        if not hasattr(model._meta, "mg_indexes"):
            model._meta.mg_indexes = {}
        return method(migrator, model, *args, **kwargs)

    return wrapper


class Migrator(object):
    """Provide migrations."""

    def __init__(self, database, schema=None):
        """Initialize the migrator."""
        if isinstance(database, pw.Proxy):
            database = database.obj

        self.database = database
        self.schema = schema
        self.orm = {}
        self.schema_migrator = SchemaMigrator.from_database(self.database)

        self.migration_set = Migration(self)

    def run(self):
        """Run operations."""
        if self.schema:
            self.migration_set.ops.insert(0, self.schema_migrator.select_schema(self.schema))
        self.migration_set.apply()
        self.clean()

    def python(self, func, *args, **kwargs):
        """Run python code."""
        self.migration_set.append(lambda: func(*args, **kwargs))

    def sql(self, sql, *params):
        """Execure raw SQL."""
        self.migration_set.append(self.schema_migrator.sql(sql, *params))

    def clean(self):
        """Clean the operations."""
        self.migration_set.clean()

    @get_model
    def create_model(self, model: ModelCls) -> ModelCls:
        """Create model and table in database.

        >> migrator.create_model(model)
        """
        self.migration_set.append(CreateModel(model))
        return model

    create_table = create_model

    @get_model
    def remove_model(self, model: ModelCls) -> None:
        """Drop model and table from database.

        >> migrator.remove_model(model)
        """

        self.migration_set.append(RemoveModel(model))

    drop_table = remove_model

    @get_model
    def add_fields(self, model: ModelCls, **fields: Any) -> None:
        """Create new fields."""
        self.migration_set.append(AddFields(model, **fields))

    add_columns = add_fields

    @get_model
    def change_fields(self, model: ModelCls, **fields: pw.Field) -> None:
        """Change fields."""

        return self.migration_set.append(ChangeFields(model, **fields))

    change_columns = change_fields

    @get_model
    def remove_fields(self, model, *names: str, cascade: bool = False) -> None:
        """Remove fields from model."""
        self.migration_set.append(RemoveFields(model, *names, cascade=cascade))

    drop_columns = remove_fields

    @get_model
    def rename_field(self, model: ModelCls, old_name: str, new_name: str) -> None:
        """Rename field in model."""

        self.migration_set.append(RenameField(model, old_name, new_name))

    rename_column = rename_field

    @get_model
    def rename_table(self, model: ModelCls, new_table_name: str) -> None:
        self.migration_set.append(RenameTable(model, new_table_name))

    rename_model = rename_table

    @get_model
    def add_index(
        self,
        model: ModelCls,
        *fields: str,
        name: str,
        unique: bool = False,
        where: pw.SQL | None = None,
        safe: bool = False,
        concurrently: bool = False,
    ) -> None:
        """Create indexes."""
        self.migration_set.append(
            AddIndex(model, *fields, name=name, unique=unique, where=where, safe=safe, concurrently=concurrently)
        )

    @get_model
    def drop_index(self, model: ModelCls, name: str) -> None:
        """Drop indexes."""
        self.migration_set.append(DropIndex(model, name))

    @get_model
    def add_not_null(self, model: ModelCls, *names: str) -> None:
        """Add not null."""
        self.migration_set.append(ChangeNullable(model, *names, is_null=False))

    @get_model
    def drop_not_null(self, model: ModelCls, *names: str) -> None:
        """Drop not null."""
        self.migration_set.append(ChangeNullable(model, *names, is_null=True))
