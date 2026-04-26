import enum
from typing import TYPE_CHECKING, Any

import peewee as pw

from miggy.deconstructor import ModelDeconstructor, deconstructor_factory
from miggy.utils import Default, get_default_constraint

if TYPE_CHECKING:
    from miggy.types import ModelCls


class BaseSerializer:
    def __init__(self, value):
        self.value = value

    def serialize(self) -> str:
        return repr(self.value)


class EnumSerializer(BaseSerializer):
    def serialize(self) -> str:
        return repr(self.value.value)


class ListSerializer(BaseSerializer):
    def _format(self) -> str:
        return "[%s]"

    def serialize(self):
        strings = []
        for item in self.value:
            strings.append(serialize_value(item))
        value = self._format()
        return value % (", ".join(strings))


class DefaultSerializer(BaseSerializer):
    def serialize(self) -> str:
        default_constraint = self.value
        return 'pw.SQL("DEFAULT %s")' % default_constraint.value.replace('"', '\\"')


class FieldSerializer:
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
        self.name = field.name
        self.field_class = self.field_deconstructor.field_type
        self.raw_column_type = field.field_type
        self.nullable = field.null
        self.primary_key = field.primary_key
        self.column_name = field.column_name
        self.index = field.index
        self.unique = field.unique
        self.extra_parameters = self.field_deconstructor.get_field_params()

    def handle_constraints(self, params: dict[str, Any]) -> None:
        field = self.field_deconstructor.field
        if field.constraints:
            default_constraint = get_default_constraint(field)
            if default_constraint is not None:
                params["constraints"] = serialize_value([default_constraint])

    def get_field_parameters(self):
        params = {}
        field = self.field_deconstructor.field
        if self.extra_parameters is not None:
            params.update(self.extra_parameters)

        # Set up default attributes.
        if self.field_class is pw.ForeignKeyField or self.name != self.column_name:
            params["column_name"] = "'%s'" % self.column_name
        if self.primary_key and not issubclass(self.field_class, pw.AutoField):
            params["primary_key"] = True

        # Handle ForeignKeyField-specific attributes.
        if self.is_foreign_key():
            params["model"] = "migrator.state['%s']" % field.rel_model._meta.name
            if field.rel_field:
                params["field"] = "'%s'" % field.rel_field.name
            if field.backref:
                params["backref"] = "'%s'" % field.backref

        # Handle indexes on column.
        if not self.is_primary_key():
            if self.unique:
                params["unique"] = "True"
            elif self.index and not self.is_foreign_key():
                params["index"] = "True"
        self.handle_constraints(params)
        return params

    def is_primary_key(self) -> bool:
        return self.field_class is pw.AutoField or self.primary_key

    def is_foreign_key(self) -> bool:
        return self.field_class is pw.ForeignKeyField

    def get_field(self) -> str:
        # Generate the field definition for this column.
        field_params = {}
        for key, value in self.get_field_parameters().items():
            if isinstance(value, pw.Field):
                value = value.__name__
            field_params[key] = value

        if "default" in field_params:
            field_params["default"] = serialize_value(field_params["default"])

        param_str = ", ".join("%s=%s" % (k, v) for k, v in sorted(field_params.items()))
        return "%s(%s)" % (self.field_class.__name__, param_str)

    def serialize(self) -> str:
        # Generate the field definition for this column.
        field = self.get_field()
        module = self.FIELD_MODULES_MAP.get(self.field_class.__name__, "pw")
        return "{module}.{field}".format(field=field, module=module)


class ModelSerializer(BaseSerializer):
    def serialize(self) -> str:
        model: ModelCls = self.value
        deconstructed = ModelDeconstructor(model).deconstruct()
        deconstructed["fields"] = {n: FieldSerializer(f).serialize for n, f in deconstructed["fields"].items()}
        # WIP
        return repr(deconstructed)


def serialize_field(field: pw.Field, add_space: bool = False) -> str:
    serialized_field = FieldSerializer(field).serialize()
    sep = " = " if add_space else "="
    return sep.join([field.name, serialized_field])


def serialize_value(value) -> str:
    if isinstance(value, enum.Enum):
        return EnumSerializer(value).serialize()
    if isinstance(value, list):
        return ListSerializer(value).serialize()
    if isinstance(value, Default):
        return DefaultSerializer(value).serialize()
    return BaseSerializer(value=value).serialize()
