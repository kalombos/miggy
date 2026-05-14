from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import peewee as pw

from miggy.ext.fields import CharEnumField, IntEnumField
from miggy.utils import Default, LazyModel, fk_postfix, get_default_constraint

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

    def is_bound(self) -> bool:
        return hasattr(self.field, "model") and hasattr(self.field, "name")

    def is_custom_column_name(self) -> bool:
        return self.field.name != self.field.column_name

    def deconstruct_column_name(self) -> dict[str, Any]:
        if self.is_bound():
            if self.is_custom_column_name():
                return {"column_name": self.field.column_name}
        else:
            if self.field.column_name is not None:
                return {"column_name": self.field.column_name}
        return {}

    def deconstruct_index(self) -> dict[str, Any]:
        params = {}
        if not self.field.primary_key:
            if self.field.unique:
                params["unique"] = True
            elif self.field.index:
                params["index"] = True
        return params

    def deconstruct_primary_key(self) -> dict[str, Any]:
        if self.field.primary_key:
            return {"primary_key": True}
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

        params["type"] = self.field_type
        params.update(self.deconstruct_column_name())
        params.update(self.deconstruct_primary_key())
        params.update(self.deconstruct_index())
        return params


class CharFieldDeconstructor(FieldDeconstructor):
    def get_type_modifiers(self) -> dict[str, Any]:
        return {"max_length": self.field.max_length}


class DecimalFieldDeconstructor(FieldDeconstructor):
    def get_type_modifiers(self) -> dict[str, Any]:
        return {"max_digits": self.field.max_digits, "decimal_places": self.field.decimal_places}


class ForeignKeyFieldDeconstructor(FieldDeconstructor):
    def deconstruct_fk_params(self) -> dict[str, Any]:
        field = self.field
        params: dict[str, Any] = {"model": LazyModel(field.rel_model._meta.name)}
        if field.on_delete:
            params["on_delete"] = field.on_delete
        if field.on_update:
            params["on_update"] = field.on_update
        if field.constraint_name:
            params["constraint_name"] = field.constraint_name

        if self.is_bound():
            if field.rel_field.name != field.rel_model._meta.primary_key.name:
                params["field"] = field.rel_field.name
        else:
            if isinstance(field.rel_field, str):
                params["field"] = field.rel_field
        return params

    def is_custom_column_name(self) -> bool:
        return self.field.column_name != fk_postfix(self.field.name)

    def deconstruct_index(self) -> dict[str, Any]:
        params = {}
        if not self.field.primary_key:
            if self.field.unique:
                params["unique"] = True
            elif not self.field.index:
                params["index"] = False
        return params

    def deconstruct(self) -> dict[str, Any]:
        params = super().deconstruct()
        params.update(self.deconstruct_fk_params())
        return params


class AutoFieldDeconstructor(FieldDeconstructor):
    def deconstruct_primary_key(self) -> dict[str, Any]:
        return {}


class ModelDeconstructor(BaseDeconstructor):
    def __init__(self, model: ModelCls) -> None:
        self.model = model

    def deconstruct(self) -> dict[str, Any]:
        model = self.model
        fields = [f for f in self.model._meta.sorted_fields if not isinstance(f, pw.AutoField)]
        meta = {}
        if model._meta.table_name != model._meta.make_table_name():
            meta["table_name"] = model._meta.table_name
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
    if isinstance(f, pw.AutoField):
        return AutoFieldDeconstructor(f)
    return FieldDeconstructor(f)


def deep_deconstruct(field: pw.Field) -> Any:
    params = deconstructor_factory(field).deconstruct()
    if "constraints" in params:
        params["constraints"] = [
            {"type": Default, "value": c.value} if isinstance(c, Default) else c for c in params["constraints"]
        ]
    return params
