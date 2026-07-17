import enum
import types
from typing import Any, NamedTuple

import peewee as pw

from miggy.deconstructor import deconstructor_factory
from miggy.utils import Default

FUNCTION_TYPES = (types.FunctionType, types.BuiltinFunctionType, types.MethodType)
PEEWEE_IMPORT = "import peewee as pw"


class SerializedCode(NamedTuple):
    code: str
    imports: set = set()


class SerializeValueMixin:
    imports: set[str]

    def serialize_value(self, value: Any) -> str:
        serialized = serializer_factory(value).serialize()
        self.imports.update(serialized.imports)
        return serialized.code


class BaseSerializer(SerializeValueMixin):
    def __init__(self, value) -> None:
        self.value = value
        self.imports = set()

    def serialize_to_code(self) -> str:
        return repr(self.value)

    def serialize(self) -> SerializedCode:
        return SerializedCode(code=self.serialize_to_code(), imports=self.imports)


class EnumSerializer(BaseSerializer):
    def serialize_to_code(self) -> str:
        return repr(self.value.value)


class FunctionTypeSerializer(BaseSerializer):
    def serialize_to_code(self) -> str:
        if getattr(self.value, "__self__", None) and isinstance(self.value.__self__, type):
            klass = self.value.__self__
            module = klass.__module__
            self.imports.add("import %s" % module)
            return "%s.%s.%s" % (module, klass.__qualname__, self.value.__name__)
        # Further error checking
        if self.value.__name__ == "<lambda>":
            raise ValueError("Cannot serialize function: lambda")
        if self.value.__module__ is None:
            raise ValueError("Cannot serialize function %r: No module" % self.value)

        module_name = self.value.__module__

        if "<" not in self.value.__qualname__:  # Qualname can include <locals>
            self.imports.add("import %s" % self.value.__module__)
            return "%s.%s" % (module_name, self.value.__qualname__)

        raise ValueError("Could not find function %s in %s.\n" % (self.value.__name__, module_name))


class BaseSequenceSerializer(BaseSerializer):
    def _format(self) -> str:
        raise NotImplementedError("Subclasses of BaseSequenceSerializer must implement the _format() method.")

    def serialize_to_code(self) -> str:
        strings = []
        for item in self.value:
            strings.append(self.serialize_value(item))
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


class SQLSerializer(BaseSerializer):
    def serialize_to_code(self) -> str:
        params = [self.serialize_value(self.value.sql)]
        if self.value.params is not None:
            params.append(self.serialize_value(self.value.params))
        self.imports.add(PEEWEE_IMPORT)
        return "pw.SQL(%s)" % ", ".join(params)


class DefaultSerializer(BaseSerializer):
    def serialize_to_code(self) -> str:
        default_constraint = self.value
        self.imports.add(PEEWEE_IMPORT)
        return "pw.SQL(%s)" % self.serialize_value(f"DEFAULT {default_constraint.value}")


class CompositeKeySerializer(BaseSerializer):
    def serialize_to_code(self) -> str:
        self.imports.add(PEEWEE_IMPORT)
        return "pw.CompositeKey(%s)" % ", ".join(self.serialize_value(n) for n in self.value.field_names)


class FieldSerializer(BaseSerializer):
    def serialize_path(self, path: str) -> str:
        module, field = path.rsplit(".", 1)
        match module:
            case "peewee":
                import_ = "import peewee as pw"
                field = f"pw.{field}"
            case "playhouse.postgres_ext":
                import_ = "import playhouse.postgres_ext as pw_pext"
                field = f"pw_pext.{field}"
            case "miggy.ext.fields":
                import_ = "import miggy.ext.fields as m_ext"
                field = f"m_ext.{field}"
            case _:
                import_ = "import %s" % module
                field = path
        self.imports.add(import_)
        return field

    def serialize_to_code(self) -> str:
        deconstructed_field = deconstructor_factory(self.value).deconstruct()
        path, params = deconstructed_field
        field = self.serialize_path(path)
        param_str = ", ".join("%s=%s" % (k, self.serialize_value(v)) for k, v in sorted(params.items()))
        return f"{field}({param_str})"


def serializer_factory(value) -> BaseSerializer:
    if isinstance(value, pw.CompositeKey):
        return CompositeKeySerializer(value)
    if isinstance(value, Default):
        return DefaultSerializer(value)
    if isinstance(value, pw.SQL):
        return SQLSerializer(value)
    if isinstance(value, pw.Field):
        return FieldSerializer(value)
    if isinstance(value, FUNCTION_TYPES):
        return FunctionTypeSerializer(value)
    if isinstance(value, enum.Enum):
        return EnumSerializer(value)
    if isinstance(value, tuple):
        return TupleSerializer(value)
    if isinstance(value, list):
        return ListSerializer(value)
    return BaseSerializer(value=value)
