import enum
from typing import TYPE_CHECKING

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
        self.field = field

    def serialize(self) -> str:
        deconstructed = deconstructor_factory(self.field).deconstruct()

        field_class = deconstructed["type"]
        del deconstructed["type"]

        param_str = ", ".join("%s=%s" % (k, serialize_value(v)) for k, v in sorted(deconstructed.items()))
        field = "%s(%s)" % (field_class.__name__, param_str)

        module = self.FIELD_MODULES_MAP.get(field_class.__name__, "pw")
        return "{module}.{field}".format(field=field, module=module)


class ModelSerializer(BaseSerializer):
    def serialize(self) -> str:
        model: ModelCls = self.value
        deconstructed = ModelDeconstructor(model).deconstruct()
        deconstructed["fields"] = {n: FieldSerializer(f).serialize() for n, f in deconstructed["fields"].items()}
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
