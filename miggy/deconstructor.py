from __future__ import annotations

from typing import TYPE_CHECKING, Any

import peewee as pw

from miggy.ext.fields import CharEnumField, IntEnumField
from miggy.utils import Default, fk_postfix, get_default_constraint

if TYPE_CHECKING:
    from miggy.types import ModelCls


from typing import NamedTuple


class DeconstructedField(NamedTuple):
    path: str
    params: dict[str, Any]


class FieldDeconstructor:
    def __init__(self, field: pw.Field) -> None:
        self.field = field

    def deconstruct_type_modifiers(self) -> dict[str, Any]:
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

    def deconstruct_params(self) -> dict[str, Any]:
        field = self.field
        params: dict[str, Any] = {}
        if self.field.null:
            params["null"] = True
        if field.default is not None:
            params["default"] = field.default
        if default_constraint := get_default_constraint(field):
            params["constraints"] = [default_constraint]

        params.update(self.deconstruct_type_modifiers())
        params.update(self.deconstruct_column_name())
        params.update(self.deconstruct_primary_key())
        params.update(self.deconstruct_index())
        return params

    def deconstruct_path(self) -> str:
        return "%s.%s" % (self.field.__class__.__module__, self.field.__class__.__qualname__)

    def deconstruct(self) -> DeconstructedField:
        return DeconstructedField(path=self.deconstruct_path(), params=self.deconstruct_params())


class CharFieldDeconstructor(FieldDeconstructor):
    def deconstruct_type_modifiers(self) -> dict[str, Any]:
        if self.field.max_length != 255:  # type: ignore[attr-defined]
            return {"max_length": self.field.max_length}  # type: ignore[attr-defined]
        return {}


class CharEnumFieldDeconstructor(CharFieldDeconstructor):
    def deconstruct_path(self) -> str:
        # turn it to CharField
        cls = pw.CharField
        return "%s.%s" % (cls.__module__, cls.__qualname__)


class IntEnumFieldDeconstructor(FieldDeconstructor):
    def deconstruct_path(self) -> str:
        # turn it to IntegerField
        cls = pw.IntegerField
        return "%s.%s" % (cls.__module__, cls.__qualname__)


class DecimalFieldDeconstructor(FieldDeconstructor):
    def deconstruct_type_modifiers(self) -> dict[str, Any]:
        return {"max_digits": self.field.max_digits, "decimal_places": self.field.decimal_places}  # type: ignore[attr-defined]


class ForeignKeyFieldDeconstructor(FieldDeconstructor):
    def deconstruct_fk_params(self) -> dict[str, Any]:
        field = self.field
        params: dict[str, Any] = {"model": field.rel_model._meta.name}  # type: ignore[attr-defined]
        if field.on_delete:  # type: ignore[attr-defined]
            params["on_delete"] = field.on_delete  # type: ignore[attr-defined]
        if field.on_update:  # type: ignore[attr-defined]
            params["on_update"] = field.on_update  # type: ignore[attr-defined]
        if field.constraint_name:  # type: ignore[attr-defined]
            params["constraint_name"] = field.constraint_name  # type: ignore[attr-defined]

        if self.is_bound():
            if field.rel_field.name != field.rel_model._meta.primary_key.name:  # type: ignore[attr-defined]
                params["field"] = field.rel_field.name  # type: ignore[attr-defined]
        else:
            if isinstance(field.rel_field, str):  # type: ignore[attr-defined]
                params["field"] = field.rel_field  # type: ignore[attr-defined]
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

    def deconstruct_params(self) -> dict[str, Any]:
        params = super().deconstruct_params()
        params.update(self.deconstruct_fk_params())
        return params


class AutoFieldDeconstructor(FieldDeconstructor):
    def deconstruct_primary_key(self) -> dict[str, Any]:
        return {}


class ModelDeconstructor:
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
    if isinstance(f, IntEnumField):
        return IntEnumFieldDeconstructor(f)
    if isinstance(f, CharEnumField):
        return CharEnumFieldDeconstructor(f)
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
    path, params = deconstructor_factory(field).deconstruct()

    if "constraints" in params:
        params["constraints"] = [
            {"type": Default, "value": c.value} if isinstance(c, Default) else c for c in params["constraints"]
        ]
    return DeconstructedField(path, params)
