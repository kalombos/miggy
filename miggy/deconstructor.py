from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import peewee as pw

from miggy.ext.fields import CharEnumField, IntEnumField
from miggy.utils import Default, get_default_constraint

if TYPE_CHECKING:
    from miggy.types import ModelCls


class BaseDeconstructor(Protocol):
    def deconstruct(self) -> dict[str, Any]: ...


class FieldDeconstructor(BaseDeconstructor):
    def __init__(self, field: pw.Field) -> None:
        self.field = field

    @property
    def field_type(self) -> type[pw.Field]:
        if isinstance(self.field, CharEnumField):
            return pw.CharField
        elif isinstance(self.field, IntEnumField):
            return pw.SmallIntegerField
        return type(self.field)

    def _get_default(self, field: pw.Field) -> Any:
        if field.default is not None and not callable(field.default):
            return field.default
        return None

    def get_type_modifiers(self) -> dict[str, Any]:
        return {}

    def deconstruct(self) -> dict[str, Any]:
        field = self.field
        params = self.get_type_modifiers()
        if self.field.null:
            params["null"] = True
        if default := self._get_default(field):
            params["default"] = default
        if default_constraint := get_default_constraint(field):
            params["constraints"] = [default_constraint]
        if field.name != field.column_name:
            params["column_name"] = field.column_name
        params["type"] = self.field_type
        params["index"] = field.index and not field.unique, field.unique
        return params


class CharFieldDeconstructor(FieldDeconstructor):
    def get_type_modifiers(self) -> dict[str, Any]:
        return {"max_length": self.field.max_length}


class DecimalFieldDeconstructor(FieldDeconstructor):
    def get_type_modifiers(self) -> dict[str, Any]:
        return {"max_digits": self.field.max_digits, "decimal_places": self.field.decimal_places}


class ForeignKeyFieldDeconstructor(FieldDeconstructor):
    @staticmethod
    def fk_to_params(field: pw.ForeignKeyField) -> dict[str, Any]:
        params = {"model": field.rel_model._meta.name}
        if field.on_delete is not None:
            params["on_delete"] = field.on_delete
        if field.on_update is not None:
            params["on_update"] = field.on_update
        if field.constraint_name is not None:
            params["constraint_name"] = field.constraint_name
        return params

    def deconstruct(self) -> dict[str, Any]:
        params = super().deconstruct()
        params.update(self.fk_to_params(self.field))
        return params


class ModelDeconstructor(BaseDeconstructor):
    def __init__(self, model: ModelCls):
        self.model = model

    def deconstruct(self) -> dict[str, Any]:
        model = self.model
        fields = [f for f in self.model._meta.sorted_fields if not isinstance(f, pw.AutoField)]
        meta = {"table_name": model._meta.table_name}
        if model._meta.schema:
            meta["schema"] = model._meta.schema
        if model._meta.primary_key and isinstance(model._meta.primary_key, pw.CompositeKey):
            meta["primary_key"] = model._meta.primary_key

        return {"name": model.__name__, "fields": {f.name: f for f in fields}, "meta": meta}


def deconstructor_factory(f: pw.Field) -> FieldDeconstructor | CharFieldDeconstructor:
    if isinstance(f, pw.ForeignKeyField):
        return ForeignKeyFieldDeconstructor(f)
    if isinstance(f, pw.CharField):
        return CharFieldDeconstructor(f)
    if isinstance(f, pw.DecimalField):
        return DecimalFieldDeconstructor(f)
    return FieldDeconstructor(f)


def deep_deconstruct(field: pw.Field) -> Any:
    params = deconstructor_factory(field).deconstruct()
    if "constraints" in params:
        params["constraints"] = [
            {"type": Default, "value": c.value} if isinstance(c, Default) else c for c in params["constraints"]
        ]
    return params
