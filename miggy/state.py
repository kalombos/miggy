from collections.abc import ValuesView
from typing import Any

import peewee as pw

from miggy.types import ModelCls
from miggy.utils import copy_model

ModelDict = dict[str, ModelCls]


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

    def __setitem__(self, key: str, val: ModelCls) -> None:
        self.data[self.normalize_key(key)] = val

    def __getitem__(self, key: str) -> ModelCls:
        return self.data[self.normalize_key(key)]

    def __delitem__(self, key: str) -> None:
        del self.data[self.normalize_key(key)]

    def __contains__(self, key: str) -> bool:
        return self.normalize_key(key) in self.data

    def values(self) -> ValuesView[ModelCls]:
        return self.data.values()

    def create_snapshot(self) -> None:
        self._snapshot = self.data.copy()

    def pop_snapshot(self) -> "State":
        _snapshot = self._snapshot
        self._snapshot = None
        return State(_snapshot)

    def add_model(self, name: str, fields: dict[str, pw.Field], meta: dict[str, Any]) -> None:
        attrs = fields.copy()
        attrs["Meta"] = type("Meta", (object,), meta)
        model = type(name, (pw.Model,), attrs)
        self[name] = model

    def remove_model(self, name: str) -> None:
        del self[name]

    def add_fields(self, model_name: str, **fields: pw.Field) -> None:
        model = self[model_name]
        for field_name, field in fields.items():
            model._meta.add_field(field_name, field)
