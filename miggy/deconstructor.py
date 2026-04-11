from __future__ import annotations

from typing import Any

import peewee as pw

from miggy.ext.fields import CharEnumField, IntEnumField
from miggy.utils import get_default_constraint_value


class FieldDeconstructor:
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

    @staticmethod
    def fk_to_params(field: pw.ForeignKeyField) -> dict[str, Any]:
        params = {"model": field.rel_model._meta.name}
        if field.on_delete is not None:
            params["on_delete"] = "'%s'" % field.on_delete
        if field.on_update is not None:
            params["on_update"] = "'%s'" % field.on_update
        if field.constraint_name is not None:
            params["constraint_name"] = "'%s'" % field.constraint_name
        return params

    def get_type_modifiers(self) -> dict[str, Any]:
        return {}

    def get_field_params(self) -> dict[str, Any]:
        params = self.get_type_modifiers()
        if self.field_type is pw.ForeignKeyField:
            params.update(self.fk_to_params(self.field))
        return params

    def deconstruct(self) -> dict[str, Any]:
        field = self.field
        params = self.get_field_params()
        params["type"] = self.field_type
        params["null"] = field.null
        params["column_name"] = field.column_name
        params["default"] = self._get_default(field)
        params["default_constraint"] = get_default_constraint_value(field)
        params["index"] = field.index and not field.unique, field.unique
        return params


class CharFieldDeconstructor(FieldDeconstructor):
    def get_type_modifiers(self) -> dict[str, Any]:
        return {"max_length": self.field.max_length}


class DecimalFieldDeconstructor(FieldDeconstructor):
    def get_type_modifiers(self) -> dict[str, Any]:
        return {"max_digits": self.field.max_digits, "decimal_places": self.field.decimal_places}


def deconstructor_factory(f: pw.Field) -> FieldDeconstructor | CharFieldDeconstructor:
    if isinstance(f, pw.CharField):
        return CharFieldDeconstructor(f)
    if isinstance(f, pw.DecimalField):
        return DecimalFieldDeconstructor(f)
    return FieldDeconstructor(f)
