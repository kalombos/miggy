from ast import Call
from typing import Callable
import peewee as pw
from functools import wraps
from playhouse.migrate import (
    MySQLMigrator as MqM,
    PostgresqlMigrator as PgM,
    SchemaMigrator as ScM,
    SqliteMigrator as SqM,
    Operation, SQL, PostgresqlDatabase, operation, SqliteDatabase, MySQLDatabase,
    make_index_name
)

from peewee_migrate import LOGGER



class MigrateOperation:

    migrator: "Migrator"

    @property
    def schema_migrator(self) -> "SchemaMigrator":
        return self.migrator.schema_migrator

    def state_forwards(self, migrator: 'Migrator') -> None:
        """
        Take the state from the previous migration, and mutate it
        so that it matches what this migration would perform.
        """

        raise NotImplementedError

    def database_forwards(self) -> Operation | Callable:
        """
        Perform the mutation on the database schema in the normal
        (forwards) direction.
        """
        raise NotImplementedError


class CreateTable(MigrateOperation):
    def __init__(self, model: pw.Model) -> None:
        self.model = model

    def state_forwards(self) -> None:
        self.migrator.orm[self.model._meta.table_name] = self.model
        

    def database_forwards(self) -> Callable:
        self.model._meta.database = self.migrator.database  # without it we can't run `model.create_table`
        return lambda: self.model.create_table()


class AddIndex(MigrateOperation):
    def __init__(self, model: pw.Model, *columns, **kwargs) -> None:
        self.model = model
        self.columns = columns
        self.unique = kwargs.pop('unique', False)

    def state_forwards(self) -> None:
        if len(self.columns) == 1:
            field = self.model._meta.fields.get(self.columns[0])
            field.unique = self.unique
            field.index = True
        else:
            self.model._meta.indexes.append((self.columns, self.unique))

    def database_forwards(self) -> Operation:
        columns = self.columns
        columns_ = []
        for col in columns:
            field = self.model._meta.fields.get(col)
            if isinstance(field, pw.ForeignKeyField):
                col = col + '_id'

            columns_.append(col)
        return self.schema_migrator.add_index(self.model._meta.table_name, columns_, unique=self.unique)


class Migration:
    def __init__(self, migrator: 'Migrator') -> None:
        self.migrator = migrator
        self.ops: list[Operation | Callable] = []

    def append(self, op: MigrateOperation) -> None:
        if isinstance(op, MigrateOperation):
            op.migrator = self.migrator
            op.state_forwards()
            self.ops.append(op.database_forwards())
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
        self.ops = list()


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

    def drop_table(self, model, cascade=True):
        return lambda: model.drop_table(cascade=cascade)

    @operation
    def change_column(self, table, column_name, field):
        """Change column."""
        operations = [self.alter_change_column(table, column_name, field)]
        if not field.null:
            operations.extend([self.add_not_null(table, column_name)])
        return operations

    def alter_change_column(self, table, column, field):
        """Support change columns."""
        ctx = self.make_context()
        field_null, field.null = field.null, True
        ctx = self._alter_table(ctx, table).literal(' ALTER COLUMN ').sql(field.ddl(ctx))
        field.null = field_null
        return ctx

    @operation
    def sql(self, sql, *params):
        """Execute raw SQL."""
        return SQL(sql, *params)

    def alter_add_column(self, table, column_name, field, **kwargs):
        """Fix fieldname for ForeignKeys."""
        name = field.name
        op = super(SchemaMigrator, self).alter_add_column(table, column_name, field, **kwargs)
        if isinstance(field, pw.ForeignKeyField):
            field.name = name
        return op


class MySQLMigrator(SchemaMigrator, MqM):

    def alter_change_column(self, table, column, field):
        """Support change columns."""
        ctx = self.make_context()
        field_null, field.null = field.null, True
        ctx = self._alter_table(ctx, table).literal(' MODIFY COLUMN ').sql(field.ddl(ctx))
        field.null = field_null
        return ctx


class PostgresqlMigrator(SchemaMigrator, PgM):

    """Support the migrations in postgresql."""

    @operation
    def select_schema(self, schema):
        """Select database schema"""
        return self.set_search_path(schema)

    def alter_change_column(self, table, column_name, field):
        """Support change columns."""
        context = super(PostgresqlMigrator, self).alter_change_column(table, column_name, field)
        context._sql.insert(-1, 'TYPE')
        context._sql.insert(-1, ' ')
        return context


class SqliteMigrator(SchemaMigrator, SqM):

    """Support the migrations in sqlite."""

    def drop_table(self, model, cascade=True):
        """SQLite doesnt support cascade syntax by default."""
        return lambda: model.drop_table(cascade=False)

    def alter_change_column(self, table, column, field):
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
            model = migrator.orm[model]

        model._meta.schema = migrator.schema
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
        self.orm = dict()
        self.schema_migrator = SchemaMigrator.from_database(self.database)


        self.migration = Migration(self)

    @property
    def ops(self) -> Migration:
        # for backward compatibility
        return self.migration  # backward compatibility
    
    @property
    def migrator(self) -> SchemaMigrator: 
        # for backward compatibility
        return self.schema_migrator 

    def run(self):
        """Run operations."""
        if self.schema:
            self.migration.ops.insert(0, self.migrator.select_schema(self.schema))
        self.migration.apply()
        self.clean()

    def python(self, func, *args, **kwargs):
        """Run python code."""
        self.ops.append(lambda: func(*args, **kwargs))

    def sql(self, sql, *params):
        """Execure raw SQL."""
        self.ops.append(self.migrator.sql(sql, *params))

    def clean(self):
        """Clean the operations."""
        self.migration.clean()

    def create_table(self, model):
        """Create model and table in database.

        >> migrator.create_table(model)
        """
        self.migration.append(CreateTable(model))
        return model

    create_model = create_table

    @get_model
    def drop_table(self, model, cascade=True):
        """Drop model and table from database.

        >> migrator.drop_table(model, cascade=True)
        """
        del self.orm[model._meta.table_name]
        self.ops.append(self.migrator.drop_table(model, cascade))

    remove_model = drop_table

    @get_model
    def add_columns(self, model, **fields):
        """Create new fields."""
        for name, field in fields.items():
            model._meta.add_field(name, field)
            self.ops.append(self.migrator.add_column(
                model._meta.table_name, field.column_name, field))
            if field.unique:
                self.ops.append(self.migrator.add_index(
                    model._meta.table_name, (field.column_name,), unique=True))
        return model

    add_fields = add_columns

    @get_model
    def change_columns(self, model, **fields):
        """Change fields."""
        for name, field in fields.items():
            old_field = model._meta.fields.get(name, field)
            old_column_name = old_field and old_field.column_name

            model._meta.add_field(name, field)

            if isinstance(old_field, pw.ForeignKeyField):
                self.ops.append(self.migrator.drop_foreign_key_constraint(
                    model._meta.table_name, old_column_name))

            if old_column_name != field.column_name:
                self.ops.append(
                    self.migrator.rename_column(
                        model._meta.table_name, old_column_name, field.column_name))

            if isinstance(field, pw.ForeignKeyField):
                on_delete = field.on_delete if field.on_delete else 'RESTRICT'
                on_update = field.on_update if field.on_update else 'RESTRICT'
                self.ops.append(self.migrator.add_foreign_key_constraint(
                    model._meta.table_name, field.column_name,
                    field.rel_model._meta.table_name, field.rel_field.name,
                    on_delete, on_update))
                continue

            self.ops.append(self.migrator.change_column(
                model._meta.table_name, field.column_name, field))

            if field.unique == old_field.unique:
                continue

            if field.unique:
                index = (field.column_name,), field.unique
                self.ops.append(self.migrator.add_index(model._meta.table_name, *index))
                model._meta.indexes.append(index)
            else:
                index = (field.column_name,), old_field.unique
                self.ops.append(self.migrator.drop_index(model._meta.table_name, *index))
                model._meta.indexes.remove(index)

        return model

    change_fields = change_columns

    @get_model
    def drop_columns(self, model, *names, **kwargs):
        """Remove fields from model."""
        fields = [field for field in model._meta.fields.values() if field.name in names]
        cascade = kwargs.pop('cascade', True)
        for field in fields:
            self.__del_field__(model, field)
            if field.unique:
                index_name = make_index_name(model._meta.table_name, [field.column_name])
                self.ops.append(self.migrator.drop_index(model._meta.table_name, index_name))
            self.ops.append(
                self.migrator.drop_column(
                    model._meta.table_name, field.column_name, cascade=cascade))
        return model

    remove_fields = drop_columns

    def __del_field__(self, model, field):
        """Delete field from model."""
        model._meta.remove_field(field.name)
        delattr(model, field.name)
        if isinstance(field, pw.ForeignKeyField):
            obj_id_name = field.column_name
            if field.column_name == field.name:
                obj_id_name += '_id'
            delattr(model, obj_id_name)
            delattr(field.rel_model, field.backref)

    @get_model
    def rename_column(self, model, old_name, new_name):
        """Rename field in model."""
        field = model._meta.fields[old_name]
        if isinstance(field, pw.ForeignKeyField):
            old_name = field.column_name
        self.__del_field__(model, field)
        field.name = field.column_name = new_name
        model._meta.add_field(new_name, field)
        if isinstance(field, pw.ForeignKeyField):
            field.column_name = new_name = field.column_name + '_id'
        self.ops.append(self.migrator.rename_column(model._meta.table_name, old_name, new_name))
        return model

    rename_field = rename_column

    @get_model
    def rename_table(self, model, new_name):
        """Rename table in database."""
        old_name = model._meta.table_name
        del self.orm[model._meta.table_name]
        model._meta.table_name = new_name
        self.orm[model._meta.table_name] = model
        self.ops.append(self.migrator.rename_table(old_name, new_name))
        return model
    
    @get_model
    def add_index(self, model, *columns, **kwargs):
        """Create indexes."""
        self.migration.append(AddIndex(model, *columns, **kwargs))
        return model

    @get_model
    def drop_index(self, model, *columns):
        """Drop indexes."""
        columns_ = []
        for col in columns:
            field = model._meta.fields.get(col)
            if not field:
                continue

            if len(columns) == 1:
                field.unique = field.index = False

            if isinstance(field, pw.ForeignKeyField):
                col = col + '_id'
            columns_.append(col)
        index_name = make_index_name(model._meta.table_name, columns_)
        model._meta.indexes = [(cols, _) for (cols, _) in model._meta.indexes if columns != cols]
        self.ops.append(self.migrator.drop_index(model._meta.table_name, index_name))
        return model

    @get_model
    def add_not_null(self, model, *names):
        """Add not null."""
        for name in names:
            field = model._meta.fields[name]
            field.null = False
            self.ops.append(self.migrator.add_not_null(model._meta.table_name, field.column_name))
        return model

    @get_model
    def drop_not_null(self, model, *names):
        """Drop not null."""
        for name in names:
            field = model._meta.fields[name]
            field.null = True
            self.ops.append(self.migrator.drop_not_null(model._meta.table_name, field.column_name))
        return model

    @get_model
    def add_default(self, model, name, default):
        """Add default."""
        field = model._meta.fields[name]
        model._meta.defaults[field] = field.default = default
        self.ops.append(self.migrator.apply_default(model._meta.table_name, name, field))
        return model

#  pylama:ignore=W0223,W0212,R
