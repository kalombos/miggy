from typing import Any

import peewee as pw

from miggy.ext.fields import CharEnumField, IntEnumField
from miggy.utils import get_default_constraint_value


class FieldDeconstructor:
    TYPE_PARAMS = {
        pw.CharField: ["max_length"],
        pw.DecimalField: ["max_digits", "decimal_places"],
    }

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

    def get_type_params(self) -> dict[str, Any]:
        params = {}
        attributes = self.TYPE_PARAMS.get(self.field_type, [])
        for attribute in attributes:
            params[attribute] = getattr(self.field, attribute)
        return params

    def get_field_params(self) -> dict[str, Any]:
        params = self.get_type_params()
        if self.field_type is pw.ForeignKeyField:
            params.update(self.fk_to_params(self.field))
        return params

    def to_params(self) -> dict[str, Any]:
        field = self.field
        params = self.get_field_params()
        params["type"] = self.field_type
        params["null"] = field.null
        params["column_name"] = field.column_name
        params["default"] = self._get_default(field)
        params["default_constraint"] = get_default_constraint_value(field)
        params["index"] = field.index and not field.unique, field.unique
        return params

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FieldDeconstructor):
            return False
        return self.to_params() == other.to_params()

    @classmethod
    def not_equal(cls, field1: pw.Field, field2: pw.Field) -> bool:
        return cls(field1) != cls(field2)
