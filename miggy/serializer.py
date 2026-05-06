import enum
from typing import TYPE_CHECKING, Any

import peewee as pw

from miggy.deconstructor import ModelDeconstructor, deconstructor_factory
from miggy.utils import Default, LazyModel

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


class LazyModelSerializer(BaseSerializer):
    def serialize(self) -> str:
        return "migrator.state['%s']" % self.value


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
        self.primary_key = field.primary_key

        params = self.field_deconstructor.deconstruct()
        self.clear_for_backward_compatibility(params)
        self.extra_parameters = params

    @staticmethod
    def clear_for_backward_compatibility(params: dict[str, Any]) -> None:
        del params["type"]

    def get_field_parameters(self) -> dict[str, Any]:
        params = self.extra_parameters

        if self.primary_key and not issubclass(self.field_class, pw.AutoField):
            params["primary_key"] = True
        return params

    def get_field(self) -> str:
        # Generate the field definition for this column.
        field_params = self.get_field_parameters()
        for name in (
            "default",
            "constraints",
            "column_name",
            "on_delete",
            "on_update",
            "constraint_name",
            "model",
            "field",
        ):
            if name in field_params:
                field_params[name] = serialize_value(field_params[name])
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
    if isinstance(value, LazyModel):
        return LazyModelSerializer(value).serialize()
    return BaseSerializer(value=value).serialize()
