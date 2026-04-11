import enum
from typing import Any

import peewee as pw
from playhouse.reflection import Column as ColumnSerializer

from miggy.deconstructor import deconstructor_factory
from miggy.utils import get_default_constraint


class BaseSerializer:
    def __init__(self, value):
        self.value = value

    def serialize(self) -> str:
        return repr(self.value)


class EnumSerializer(BaseSerializer):
    def serialize(self) -> str:
        return repr(self.value.value)


def serialize_value(value):
    if isinstance(value, enum.Enum):
        return EnumSerializer(value).serialize()
    return BaseSerializer(value=value).serialize()


class FieldSerializer(ColumnSerializer):
    FIELD_MODULES_MAP = {
        "ArrayField": "pw_pext",
        "BinaryJSONField": "pw_pext",
        "DateTimeTZField": "pw_pext",
        "HStoreField": "pw_pext",
        "IntervalField": "pw_pext",
        "JSONField": "pw_pext",
        "TSVectorField": "pw_pext",
    }

    def __init__(self, field: pw.Field) -> None:
        self.field_deconstructor = deconstructor_factory(field)
        super(FieldSerializer, self).__init__(
            field.name,
            self.field_deconstructor.field_type,
            field.field_type,
            field.null,
            primary_key=field.primary_key,
            column_name=field.column_name,
            index=field.index,
            unique=field.unique,
            extra_parameters={},
        )
        self.extra_parameters.update(self.field_deconstructor.get_field_params())

        self.rel_model = None
        self.related_name = None
        self.to_field = None

        if isinstance(field, pw.ForeignKeyField):
            self.to_field = field.rel_field.name
            self.related_name = field.backref
            self.rel_model = "migrator.state['%s']" % field.rel_model._meta.name

    def handle_default(self, params: dict[str, Any]) -> None:
        field = self.field_deconstructor.field
        default = field.default
        if default is not None and not callable(default):
            params["default"] = serialize_value(default)

    def handle_constraints(self, params: dict[str, Any]) -> None:
        # original method put value from default in constraints so override this logic
        params.pop("constraints", None)
        field = self.field_deconstructor.field
        if field.constraints:
            default_constraint = get_default_constraint(field)
            if default_constraint is not None:
                params["constraints"] = '[pw.SQL("DEFAULT %s")]' % default_constraint.value.replace('"', '\\"')

    def get_field_parameters(self) -> dict[str, Any]:
        params = super(FieldSerializer, self).get_field_parameters()
        self.handle_constraints(params)
        self.handle_default(params)
        return params

    def serialize(self, space=" ") -> str:
        # Generate the field definition for this column.
        field = self.get_field()
        module = self.FIELD_MODULES_MAP.get(self.field_class.__name__, "pw")
        name, _, field = [s and s.strip() for s in field.partition("=")]
        return "{name}{space}={space}{module}.{field}".format(name=name, field=field, space=space, module=module)

    @classmethod
    def to_code(cls, field, space=True) -> str:
        serializer = cls(field)
        return serializer.serialize(" " if space else "")
