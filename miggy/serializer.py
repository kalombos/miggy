import enum

import peewee as pw

from miggy.deconstructor import deconstructor_factory
from miggy.utils import Default, LazyModel


class BaseSerializer:
    def __init__(self, value):
        self.value = value

    def serialize(self) -> str:
        return repr(self.value)


class EnumSerializer(BaseSerializer):
    def serialize(self) -> str:
        return repr(self.value.value)


class BaseSequenceSerializer(BaseSerializer):
    def _format(self) -> str:
        raise NotImplementedError("Subclasses of BaseSequenceSerializer must implement the _format() method.")

    def serialize(self):
        strings = []
        for item in self.value:
            strings.append(serialize_value(item))
        value = self._format()
        return value % (", ".join(strings))


class ListSerializer(BaseSequenceSerializer):
    def _format(self) -> str:
        return "[%s]"


class TupleSerializer(BaseSequenceSerializer):
    def _format(self):
        # When len(value)==0, the empty tuple should be serialized as "()",
        # not "(,)" because (,) is invalid Python syntax.
        return "(%s)" if len(self.value) != 1 else "(%s,)"


class DefaultSerializer(BaseSerializer):
    def serialize(self) -> str:
        default_constraint = self.value
        return 'pw.SQL("DEFAULT %s")' % default_constraint.value.replace('"', '\\"')


class LazyModelSerializer(BaseSerializer):
    def serialize(self) -> str:
        return "migrator.state['%s']" % self.value


class CompositeKeySerializer(BaseSerializer):
    def serialize(self) -> str:
        return "pw.CompositeKey(%s)" % ", ".join(serialize_value(n) for n in self.value.field_names)


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


def serialize_field(field: pw.Field, add_space: bool = False) -> str:
    serialized_field = FieldSerializer(field).serialize()
    sep = " = " if add_space else "="
    return sep.join([field.name, serialized_field])


def serialize_value(value) -> str:
    if isinstance(value, pw.CompositeKey):
        return CompositeKeySerializer(value).serialize()
    if isinstance(value, pw.Field):
        return FieldSerializer(value).serialize()
    if isinstance(value, enum.Enum):
        return EnumSerializer(value).serialize()
    if isinstance(value, tuple):
        return TupleSerializer(value).serialize()
    if isinstance(value, list):
        return ListSerializer(value).serialize()
    if isinstance(value, Default):
        return DefaultSerializer(value).serialize()
    if isinstance(value, LazyModel):
        return LazyModelSerializer(value).serialize()
    return BaseSerializer(value=value).serialize()
