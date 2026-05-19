import collections
from collections.abc import Sequence
from typing import Any, NamedTuple

import peewee as pw

from miggy.deconstructor import deep_deconstruct
from miggy.operations import AddFields, AddIndex, DropIndex, MigrateOperation, RemoveFields, RemoveModel, RenameTable
from miggy.serializer import serialize_field
from miggy.utils import ModelIndex, indexes_state, resolve_field

from .types import ModelCls

INDENT = "    "
NEWLINE = "\n" + INDENT


class IndexMeta(NamedTuple):
    model: str
    fields: tuple[str, ...]
    name: str
    unique: bool = False
    where: str | None = None

    def as_operation(self) -> AddIndex:
        kwargs = {}

        if self.unique:
            kwargs["unique"] = True

        if self.where is not None:
            kwargs["where"] = pw.SQL(self.where)

        return AddIndex(self.model, *self.fields, name=self.name, **kwargs)


class IndexMetaExtractor:
    def __init__(self, model_cls: ModelCls, index_obj: ModelIndex) -> None:
        self.model_cls = model_cls
        self.index_obj = index_obj

    def resolve_where(self, where: pw.Node | None) -> None | str:
        if isinstance(where, pw.SQL):
            if where.params is not None:
                raise NotImplementedError(
                    "SQL object with params for where condition is not suported. Use SQL object without params instead."
                )
            return where.sql
        if where is None:
            return None
        raise NotImplementedError(
            f"{type(where)} for where condition is not suported. Use SQL object without params instead."
        )

    def validate_fields(self, model_index: pw.ModelIndex) -> None:
        for f in model_index._expressions:
            if not isinstance(f, pw.Field):
                raise NotImplementedError(f"{type(f)} for ModelIndex.field is not suported. Use Field object instead.")

    def serialize(self) -> IndexMeta:
        model_index = self.index_obj
        self.validate_fields(model_index)
        return IndexMeta(
            self.model_cls._meta.name,
            tuple(f.name for f in model_index._expressions),
            unique=model_index._unique,
            where=self.resolve_where(model_index._where),
            name=model_index._name,
        )


def extract_index_meta(model_cls: ModelCls) -> list[IndexMeta]:
    rebuild_indexes(model_cls)
    indexes = indexes_state(model_cls).values()
    return [IndexMetaExtractor(model_cls, i).serialize() for i in indexes]


def rebuild_indexes(model_cls: ModelCls) -> None:
    def resolve_fields(fields: Sequence[Any]) -> tuple[str, ...]:
        _fields = []
        for field in fields:
            if isinstance(field, str):
                field = resolve_field(model_cls, field)
            if isinstance(field, pw.Field):
                _fields.append(field)
            else:
                raise NotImplementedError
        return tuple(_fields)

    for index_obj in model_cls._meta.indexes:
        # Advanced Indexes
        # https://docs.peewee-orm.com/en/latest/peewee/models.html#advanced-index-creation
        if isinstance(index_obj, pw.ModelIndex):
            indexes_state(model_cls)[index_obj._name] = index_obj

        # Multi-column indexes
        # https://docs.peewee-orm.com/en/latest/peewee/models.html#multi-column-indexes
        elif isinstance(index_obj, (list, tuple)):
            fields, unique = index_obj
            model_index = ModelIndex(model_cls, resolve_fields(fields), unique=unique)
            indexes_state(model_cls)[model_index._name] = model_index
        else:
            raise NotImplementedError(
                f"{type(index_obj)} as Index is not suported. Use ModelIndex, list or tuple instead."
            )
    model_cls._meta.indexes = []


def diff_indexes_from_meta(current: ModelCls, prev: ModelCls) -> tuple[list[AddIndex], list[DropIndex]]:
    create_changes = []
    drop_changes = []
    current_indexes = extract_index_meta(current)
    prev_indexes = extract_index_meta(prev)

    for index_meta in set(current_indexes) - set(prev_indexes):
        create_changes.append(index_meta.as_operation())
    for index_meta in set(prev_indexes) - set(current_indexes):
        drop_changes.append(DropIndex(prev._meta.name, index_meta.name))
    return create_changes, drop_changes


def _primary_key_last(fields: list[pw.Field]) -> list[pw.Field]:
    _fields = []
    pk_field = None
    for f in fields:
        if f.primary_key:
            pk_field = f
        else:
            _fields.append(f)
    if pk_field:
        _fields.append(pk_field)
    return _fields


def diff_one(current: ModelCls, prev: ModelCls) -> list[str | MigrateOperation]:
    """Find difference between given peewee models."""
    changes: list[str | MigrateOperation] = []

    fields1 = current._meta.fields
    fields2 = prev._meta.fields

    if current._meta.table_name != prev._meta.table_name:
        changes.append(RenameTable(prev._meta.name, current._meta.table_name))

    create_index_changes, drop_index_changes = diff_indexes_from_meta(current, prev)

    # Drop non-field indexes before dropping and creating fields
    changes.extend(drop_index_changes)

    # Add fields
    names1 = set(fields1) - set(fields2)
    if names1:
        fields = {name: fields1[name] for name in names1}
        changes.append(AddFields(current._meta.name, **fields))

    # Drop fields
    names2 = set(fields2) - set(fields1)
    if names2:
        changes.append(RemoveFields(current._meta.name, *names2))

    # Change fields
    fields_ = []
    for name in set(fields1) - names1 - names2:
        field1, field2 = fields1[name], fields2[name]
        if deep_deconstruct(field1) != deep_deconstruct(field2):
            fields_.append(field1)

    if fields_:
        fields_ = _primary_key_last(fields_)
        changes.append(change_fields(current, *_primary_key_last(fields_)))

    # Create non-field indexes after dropping and creating fields
    changes.extend(create_index_changes)

    return changes


def diff_many(current_models, prev_models, reverse=False):
    """Calculate changes for migrations from models2 to models1."""
    if reverse:
        prev_models, current_models = current_models, prev_models
    current_models = pw.sort_models(current_models)
    prev_models = pw.sort_models(prev_models)

    if reverse:
        current_models = reversed(current_models)
        prev_models = reversed(prev_models)

    current_models = collections.OrderedDict([(m._meta.name, m) for m in current_models])
    prev_models = collections.OrderedDict([(m._meta.name, m) for m in prev_models])

    changes = []

    for name, current_model in current_models.items():
        # Add new models
        if name not in prev_models:
            index_meta = extract_index_meta(current_models[name])
            changes.append(create_model(current_models[name]))
            for i in index_meta:
                changes.append(i.as_operation())
        # Change existing models
        else:
            prev_model = prev_models[name]
            changes += diff_one(current_model, prev_model)

    # Remove models
    for name in [m for m in prev_models if m not in current_models]:
        changes.append(RemoveModel(prev_models[name]._meta.name))

    return changes


class MigrationAutodetector:
    def __init__(self, from_state: list[ModelCls], to_state: list[ModelCls], reverse: bool = False) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.reverse = reverse

    def changes(self):
        return diff_many(self.to_state, self.from_state, reverse=self.reverse)


def model_to_code(Model) -> str:
    template = """class {classname}(pw.Model):
{fields}

{meta}
"""
    fields = INDENT + NEWLINE.join(
        [
            serialize_field(field, add_space=True)
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
            ],
        )
    )

    return template.format(classname=Model.__name__, fields=fields, meta=meta)


def create_model(model: ModelCls) -> str:
    return "@migrator.create_model\n" + model_to_code(model)


def change_fields(model: ModelCls, *fields) -> str:
    return "migrator.change_fields('%s', %s)" % (
        model._meta.name,
        ("," + NEWLINE).join([serialize_field(f) for f in fields]),
    )
