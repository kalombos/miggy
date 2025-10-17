import collections
from collections.abc import Sequence
from typing import Any, NamedTuple, cast

import peewee as pw
from playhouse.reflection import Column as ColumnSerializer

from peewee_migrate.types import ModelCls
from peewee_migrate.utils import get_default_constraint, get_default_constraint_value

from . import types

INDENT = "    "
NEWLINE = "\n" + INDENT
FIELD_MODULES_MAP = {
    "ArrayField": "pw_pext",
    "BinaryJSONField": "pw_pext",
    "DateTimeTZField": "pw_pext",
    "HStoreField": "pw_pext",
    "IntervalField": "pw_pext",
    "JSONField": "pw_pext",
    "TSVectorField": "pw_pext",
}


def fk_to_params(field):
    params = {}
    if field.on_delete is not None:
        params["on_delete"] = "'%s'" % field.on_delete
    if field.on_update is not None:
        params["on_update"] = "'%s'" % field.on_update
    return params


FIELD_TO_PARAMS = {
    pw.CharField: lambda f: {"max_length": f.max_length},
    pw.DecimalField: lambda f: {
        "max_digits": f.max_digits,
        "decimal_places": f.decimal_places,
    },
    pw.ForeignKeyField: fk_to_params,
}


def field_to_code(field, space=True) -> str:
    serializer = FieldSerializer(field)
    return serializer.serialize(" " if space else "")


def _get_default(field: pw.Field) -> Any:
    if field.default is not None and not callable(field.default):
        return field.default
    return None


def field_to_params(field: pw.Field) -> dict[str, Any]:
    params = FIELD_TO_PARAMS.get(type(field), lambda f: {})(field)
    params["type"] = type(field)
    params["null"] = field.null
    params["column_name"] = field.column_name
    params["default"] = _get_default(field)
    params["default_constraint"] = get_default_constraint_value(field)
    params["index"] = field.index and not field.unique, field.unique
    return params


def fields_not_equal(field1, field2) -> bool:
    return field_to_params(field1) != field_to_params(field2)


class FieldSerializer(ColumnSerializer):
    def __init__(self, field: pw.Field) -> None:
        self.field = field
        super(FieldSerializer, self).__init__(
            field.name,
            type(field),
            field.field_type,
            field.null,
            primary_key=field.primary_key,
            column_name=field.column_name,
            index=field.index,
            unique=field.unique,
            extra_parameters={},
        )
        if field.default is not None and not callable(field.default):
            self.default = repr(field.default)

        if self.field_class in FIELD_TO_PARAMS:
            self.extra_parameters.update(FIELD_TO_PARAMS[self.field_class](field))

        self.rel_model = None
        self.related_name = None
        self.to_field = None

        if isinstance(field, pw.ForeignKeyField):
            self.to_field = field.rel_field.name
            self.related_name = field.backref
            self.rel_model = "migrator.orm['%s']" % field.rel_model._meta.table_name

    def get_field_parameters(self) -> dict[str, Any]:
        params = super(FieldSerializer, self).get_field_parameters()
        # original method put value from default in constraints so override this logic
        params.pop("constraints", None)
        if self.field.constraints:
            default_constraint = get_default_constraint(self.field)
            if default_constraint is not None:
                params["constraints"] = '[pw.SQL("DEFAULT %s")]' % default_constraint.value.replace('"', '\\"')
        if self.default is not None:
            params["default"] = self.default
        return params

    def serialize(self, space=" ") -> str:
        # Generate the field definition for this column.
        field = self.get_field()
        module = FIELD_MODULES_MAP.get(self.field_class.__name__, "pw")
        name, _, field = [s and s.strip() for s in field.partition("=")]
        return "{name}{space}={space}{module}.{field}".format(name=name, field=field, space=space, module=module)


class IndexMeta(NamedTuple):
    table_name: str
    columns: tuple[str, ...]
    unique: bool = False
    where: str | None = None


class IndexMetaExtractor:
    def __init__(self, model: ModelCls) -> None:
        self.model = model

    def resolve_columns(self, columns: Sequence[Any]) -> tuple[str, ...]:
        _columns = []
        for column in columns:
            if isinstance(column, str):
                _columns.append(column)
            elif isinstance(column, pw.Field):
                _columns.append(column.name)
            else:
                raise NotImplementedError
        return tuple(_columns)

    def resolve_where(self, where: pw.Node | None) -> None | str:
        if isinstance(where, pw.SQL):
            if where.params is not None:
                raise NotImplementedError(
                    "SQL object with params for where condition is not suported. Use SQL object without params instead"
                )
            return where.sql
        if where is None:
            return None
        raise NotImplementedError(
            f"{type(where)} for where condition is not suported. Use SQL object without params instead"
        )

    def extract(self) -> list[IndexMeta]:
        indexes = []
        model = self.model
        table_name = model._meta.table_name
        for index_obj in model._meta.indexes:
            # Advanced Indexes
            # https://docs.peewee-orm.com/en/latest/peewee/models.html#advanced-index-creation
            if isinstance(index_obj, pw.ModelIndex):
                i: types.ModelIndex = cast("types.ModelIndex", index_obj)
                indexes.append(
                    IndexMeta(
                        table_name,
                        self.resolve_columns(i._expressions),
                        unique=i._unique,
                        where=self.resolve_where(i._where),
                    )
                )
            # Multi-column indexes
            # https://docs.peewee-orm.com/en/latest/peewee/models.html#multi-column-indexes
            if isinstance(index_obj, (list, tuple)):
                columns, unique = index_obj
                indexes.append(IndexMeta(table_name, self.resolve_columns(columns), unique=unique))
        return indexes


def extract_index_meta(model: ModelCls) -> list[IndexMeta]:
    return IndexMetaExtractor(model).extract()


def diff_indexes_from_meta(current: ModelCls, prev: ModelCls) -> tuple[list[str], list[str]]:
    create_changes = []
    drop_changes = []
    current_indexes = extract_index_meta(current)
    prev_indexes = extract_index_meta(prev)

    for index in set(current_indexes) - set(prev_indexes):
        create_changes.append(add_index(current, *index.columns, unique=index.unique, where=index.where))
    for index in set(prev_indexes) - set(current_indexes):
        drop_changes.append(drop_index(prev, *index.columns))
    return create_changes, drop_changes


def diff_one(model1: ModelCls, model2: ModelCls) -> list[str]:
    """Find difference between given peewee models."""
    changes = []

    fields1 = model1._meta.fields
    fields2 = model2._meta.fields

    create_index_changes, drop_index_changes = diff_indexes_from_meta(model1, model2)

    # Drop non-field indexes before dropping and creating fields
    changes.extend(drop_index_changes)

    # Add fields
    names1 = set(fields1) - set(fields2)
    if names1:
        fields = [fields1[name] for name in names1]
        changes.append(create_fields(model1, *fields))

    # Drop fields
    names2 = set(fields2) - set(fields1)
    if names2:
        changes.append(drop_fields(model1, *names2))

    # Change fields
    fields_ = []
    for name in set(fields1) - names1 - names2:
        field1, field2 = fields1[name], fields2[name]
        if fields_not_equal(field1, field2):
            fields_.append(field1)

    if fields_:
        changes.append(change_fields(model1, *fields_))

    # Create non-field indexes after dropping and creating fields
    changes.extend(create_index_changes)

    return changes


def diff_many(models1, models2, reverse=False):
    """Calculate changes for migrations from models2 to models1."""
    models1 = pw.sort_models(models1)
    models2 = pw.sort_models(models2)

    if reverse:
        models1 = reversed(models1)
        models2 = reversed(models2)

    models1 = collections.OrderedDict([(m._meta.name, m) for m in models1])
    models2 = collections.OrderedDict([(m._meta.name, m) for m in models2])

    changes = []

    for name, model1 in models1.items():
        if name not in models2:
            continue
        changes += diff_one(model1, models2[name])

    # Add models
    for name in [m for m in models1 if m not in models2]:
        changes.append(create_model(models1[name]))

    # Remove models
    for name in [m for m in models2 if m not in models1]:
        changes.append(remove_model(models2[name]))

    return changes


def model_to_code(Model):
    template = """class {classname}(pw.Model):
{fields}

{meta}
"""
    fields = INDENT + NEWLINE.join(
        [
            field_to_code(field)
            for field in Model._meta.sorted_fields
            if not (isinstance(field, pw.PrimaryKeyField) and field.name == "id")
        ]
    )
    meta = INDENT + NEWLINE.join(
        filter(
            None,
            [
                "class Meta:",
                INDENT + 'table_name = "%s"' % Model._meta.table_name,
                (INDENT + 'schema = "%s"' % Model._meta.schema) if Model._meta.schema else "",
                (INDENT + "primary_key = pw.CompositeKey{0}".format(Model._meta.primary_key.field_names))
                if isinstance(Model._meta.primary_key, pw.CompositeKey)
                else "",
                (INDENT + "indexes = %s" % Model._meta.indexes) if Model._meta.indexes else "",
            ],
        )
    )

    return template.format(classname=Model.__name__, fields=fields, meta=meta)


def create_model(Model):
    return "@migrator.create_model\n" + model_to_code(Model)


def remove_model(Model):
    return "migrator.remove_model('%s')" % Model._meta.table_name


def create_fields(Model, *fields):
    return "migrator.add_fields(%s'%s', %s)" % (
        NEWLINE,
        Model._meta.table_name,
        NEWLINE + ("," + NEWLINE).join([field_to_code(field, False) for field in fields]),
    )


def drop_fields(Model, *fields) -> str:
    return "migrator.remove_fields('%s', %s)" % (Model._meta.table_name, ", ".join(map(repr, fields)))


def change_fields(Model, *fields):
    return "migrator.change_fields('%s', %s)" % (
        Model._meta.table_name,
        ("," + NEWLINE).join([field_to_code(f, False) for f in fields]),
    )


def change_not_null(Model, name, null):
    operation = "drop_not_null" if null else "add_not_null"
    return "migrator.%s('%s', %s)" % (operation, Model._meta.table_name, repr(name))


def add_index(model: types.ModelCls, *columns: str, unique: bool = False, where: str | None = None) -> str:
    operation = "add_index"
    table_name = model._meta.table_name
    if where is None:
        return "migrator.%s('%s', %s, unique=%s)" % (operation, table_name, ", ".join(map(repr, columns)), unique)
    return "migrator.%s('%s', %s, unique=%s, where=pw.SQL(%s))" % (
        operation,
        table_name,
        ", ".join(map(repr, columns)),
        unique,
        repr(where),
    )


def drop_index(model: types.ModelCls, *columns: str) -> str:
    table_name = model._meta.table_name
    operation = "drop_index"
    return "migrator.%s('%s', %s)" % (operation, table_name, ", ".join(map(repr, columns)))
