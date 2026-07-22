from collections.abc import Generator, ItemsView, ValuesView
from typing import Any

import peewee as pw

from miggy.types import ModelCls
from miggy.utils import copy_model

ModelDict = dict[str, ModelCls]


COMPOSITE_KEY_NAME = "__composite_key__"


class State:
    """
    Current state containing historical models that match the operation’s place in the project history.
    This is a dict-like class that stores data in the format model_name: model_class.
    The model_name is case-insensitive.

    Example::

        User = state["user"]
        User.get(id=1)
    """

    def __init__(self, data: ModelDict | None = None) -> None:
        self.data: ModelDict = data or {}
        self._snapshot: ModelDict | None = None

    def normalize_key(self, key: str) -> str:
        _key = key.lower()
        if self._snapshot is not None:
            if _key in self._snapshot:
                self._snapshot[_key] = copy_model(self._snapshot[_key])
        return _key

    def __iter__(self) -> Generator[str, None]:
        for name in self.data:
            yield name

    def __setitem__(self, key: str, val: ModelCls) -> None:
        self.data[self.normalize_key(key)] = val

    def __getitem__(self, key: str) -> ModelCls:
        return self.data[self.normalize_key(key)]

    def __delitem__(self, key: str) -> None:
        del self.data[self.normalize_key(key)]

    def __contains__(self, key: str) -> bool:
        return self.normalize_key(key) in self.data

    def items(self) -> ItemsView[str, ModelCls]:
        return self.data.items()

    def values(self) -> ValuesView[ModelCls]:
        return self.data.values()

    def create_snapshot(self) -> None:
        self._snapshot = self.data.copy()

    def pop_snapshot(self) -> "State":
        _snapshot = self._snapshot
        self._snapshot = None
        return State(_snapshot)

    def add_model(self, name: str, fields: dict[str, pw.Field], meta: dict[str, Any]) -> None:
        attrs: dict[str, Any] = {"Meta": type("Meta", (object,), meta)}
        for field_name, field in fields.items():
            self._resolve_relation(field)
            attrs[field_name] = field
        model = type(name, (pw.Model,), attrs)
        self[name] = model

    def remove_model(self, name: str) -> None:
        del self[name]

    def _resolve_relation(self, field: pw.Field) -> None:
        if isinstance(field, pw.ForeignKeyField):
            rel_model = field.rel_model
            if isinstance(rel_model, str) and rel_model != "self":
                field.rel_model = self[rel_model]

    def add_composite_key(self, model_name: str, field: pw.CompositeKey) -> None:
        model = self[model_name]
        model._meta.set_primary_key(COMPOSITE_KEY_NAME, field)

    def remove_composite_key(self, model_name: str) -> None:
        model = self[model_name]
        delattr(model, COMPOSITE_KEY_NAME)
        model._meta.composite_key = None
        model._meta.primary_key = False

    def add_field(self, model_name: str, name: str, field: pw.Field) -> None:
        model = self[model_name]
        self._resolve_relation(field)
        if field.primary_key:
            model._meta.set_primary_key(name, field)
        else:
            model._meta.add_field(name, field)

    def remove_field(self, model_name: str, name: str) -> None:
        model = self[model_name]
        field = model._meta.fields[name]
        model._meta.remove_field(field.name)
        delattr(model, name)
        if field.primary_key:
            model._meta.primary_key = False
        if isinstance(field, pw.ForeignKeyField):
            delattr(model, field.object_id_name)
            delattr(field.rel_model, field.backref)

    def clone(self) -> "State":
        return State({n: copy_model(m) for n, m in self.items()})
