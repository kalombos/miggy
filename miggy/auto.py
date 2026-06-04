from collections.abc import Sequence
from functools import lru_cache
from graphlib import TopologicalSorter
from typing import Any, NamedTuple

import peewee as pw

from miggy.deconstructor import ModelDeconstructor, deep_deconstruct
from miggy.operations import (
    AddField,
    AddIndex,
    AddPrimaryKeyConstraint,
    AlterField,
    CreateModel,
    Dependency,
    DropIndex,
    MigrateOperation,
    RemoveField,
    RemoveModel,
    RemovePrimaryKeyConstraint,
    RenameTable,
)
from miggy.state import State
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


def _get_primary_keys(m: ModelCls):
    meta = m._meta
    if meta.composite_key:
        return meta.primary_key.field_names
    if meta.primary_key is not False:
        return meta.primary_key.name
    return None


class MigrationAutodetector:
    def __init__(self, from_state: State, to_state: State) -> None:
        self.from_state = from_state
        self.to_state = to_state

    def _sort_operations(self, operations: list[MigrateOperation]) -> list[MigrateOperation]:
        """
        Reorder to make things possible. Reordering may be needed so FKs work
        nicely inside the same app.
        """
        ts: TopologicalSorter = TopologicalSorter()
        for op in operations:
            ts.add(op)
            for dep in op.deps:
                ts.add(op, *(x for x in operations if self.check_dependency(x, dep)))
        return list(ts.static_order())

    def check_dependency(self, operation, dependency):
        """
        Return True if the given operation depends on the given dependency,
        False otherwise.
        """
        if dependency.type == Dependency.Type.REMOVE_PK:
            if isinstance(operation, RemovePrimaryKeyConstraint):
                return operation.model_name == dependency.model_name
            return (isinstance(operation, RemoveField) or isinstance(operation, AlterField)) and self.is_old_pk(
                operation.name, operation.model_name
            )

        if dependency.type == Dependency.Type.CREATE:
            return (
                isinstance(operation, AddField)
                and operation.model_name == dependency.model_name
                and operation.name == dependency.field_name
            )

        raise ValueError("Can't handle dependency %r" % (dependency,))

    @lru_cache  # noqa: B019
    def is_old_pk(self, field_name: str, model_name: str) -> list[Dependency]:
        old_pks = _get_primary_keys(self.from_state[model_name])
        new_pks = _get_primary_keys(self.to_state[model_name])
        return old_pks != new_pks and old_pks == field_name

    @lru_cache  # noqa: B019
    def is_new_pk(self, field_name: str, model_name: str) -> list[Dependency]:
        old_pks = _get_primary_keys(self.from_state[model_name])
        new_pks = _get_primary_keys(self.to_state[model_name])
        return old_pks != new_pks and new_pks == field_name

    def generate_added_fields(self, model_name: str) -> list[AddField]:
        prev = self.from_state[model_name]
        current = self.to_state[model_name]

        prev_fields = prev._meta.fields
        current_fields = current._meta.fields
        changes = []
        for name in set(current_fields) - set(prev_fields):
            o = AddField(model_name=model_name, name=name, field=current_fields[name])
            if self.is_new_pk(name, model_name):
                o.deps.append(Dependency(model_name, None, Dependency.Type.REMOVE_PK))
            changes.append(o)
        return changes

    def generate_removed_fields(self, model_name: str) -> list[RemoveField]:
        prev = self.from_state[model_name]
        current = self.to_state[model_name]

        prev_fields = prev._meta.fields
        current_fields = current._meta.fields
        changes = []
        for name in set(prev_fields) - set(current_fields):
            op = RemoveField(model_name=model_name, name=name)
            # We make removing pk constraint first before removing fields
            # except the field is the single pk field to avoid cycle dependency
            if not self.is_old_pk(name, model_name):
                op.deps.append(Dependency(model_name, name, Dependency.Type.REMOVE_PK))
            changes.append(op)
        return changes

    def generate_altered_fields(self, model_name: str) -> list[AlterField]:
        prev = self.from_state[model_name]
        current = self.to_state[model_name]

        prev_fields = prev._meta.fields
        current_fields = current._meta.fields
        changes = []
        for name in set(current_fields).intersection(prev_fields):
            current_field, prev_field = current_fields[name], prev_fields[name]
            if deep_deconstruct(current_field) != deep_deconstruct(prev_field):
                o = AlterField(model_name=model_name, name=name, field=current_field)
                if self.is_new_pk(name, model_name):
                    o.deps.append(Dependency(model_name, None, Dependency.Type.REMOVE_PK))
                changes.append(o)
        return changes

    def generate_altered_primary_keys(self, model_name: str) -> list[MigrateOperation]:
        prev = self.from_state[model_name]
        current = self.to_state[model_name]

        prev_has_composite = bool(prev._meta.composite_key)
        current_has_composite = bool(current._meta.composite_key)

        ops: list[MigrateOperation] = []

        if prev_has_composite:
            prev_fields = prev._meta.primary_key.field_names
            if not current_has_composite or prev_fields != current._meta.primary_key.field_names:
                ops.append(RemovePrimaryKeyConstraint(model_name))

        if current_has_composite:
            current_fields = current._meta.primary_key.field_names
            if not prev_has_composite or prev._meta.primary_key.field_names != current_fields:
                op = AddPrimaryKeyConstraint(model_name, *current_fields)
                for f in current_fields:
                    op.deps.append(Dependency(model_name, f, Dependency.Type.CREATE))
                ops.append(op)

        return ops

    def diff_one(self, model_name: str) -> list[MigrateOperation]:
        """Find difference between given peewee models."""

        prev = self.from_state[model_name]
        current = self.to_state[model_name]
        ops: list[MigrateOperation] = []

        if current._meta.table_name != prev._meta.table_name:
            ops.append(RenameTable(prev._meta.name, current._meta.table_name))

        create_index_ops, drop_index_ops = diff_indexes_from_meta(current, prev)

        # Drop non-field indexes before dropping and creating fields
        ops.extend(drop_index_ops)

        field_ops: list[MigrateOperation] = []
        field_ops.extend(self.generate_altered_primary_keys(model_name))
        field_ops.extend(self.generate_added_fields(model_name))
        field_ops.extend(self.generate_removed_fields(model_name))
        field_ops.extend(self.generate_altered_fields(model_name))
        field_ops = self._sort_operations(field_ops)

        ops.extend(field_ops)
        # Create non-field indexes after dropping and creating fields
        ops.extend(create_index_ops)

        return ops

    def diff_many(self) -> list[MigrateOperation]:
        """Calculate changes for migrations from models2 to models1."""

        current_models = pw.sort_models(self.to_state.values())
        prev_models = pw.sort_models(self.from_state.values())

        from_state = State({m._meta.name: m for m in prev_models})
        to_state = State({m._meta.name: m for m in current_models})

        changes: list[MigrateOperation] = []

        for name in to_state:
            # Add new models
            if name not in from_state:
                index_meta = extract_index_meta(to_state[name])
                deconstructed = ModelDeconstructor(to_state[name]).deconstruct()
                changes.append(CreateModel(**deconstructed))
                for i in index_meta:
                    changes.append(i.as_operation())
            # Change existing models
            else:
                changes += self.diff_one(name)

        # Remove models
        for name in [m for m in from_state if m not in to_state]:
            changes.append(RemoveModel(from_state[name]._meta.name))

        return changes

    def changes(self) -> list[MigrateOperation]:
        return self.diff_many()
