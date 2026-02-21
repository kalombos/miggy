from enum import Enum, IntEnum
from typing import Any

import peewee as pw

from miggy.ext.utils import StrEnum


class BaseEnumField(pw.Field):
    """Поле для Enum для моделей peewee ORM."""

    def __init__(self, enum: type[Enum], **kwargs: Any) -> None:
        self._enum = enum
        self.value = None
        choices = [(e.value, e.name) for e in enum]
        super().__init__(choices=choices, **kwargs)

    def db_value(self, value: Any) -> Any:
        if value is None:
            return value

        value = self._enum(value)
        return value.value

    def python_value(self, value: Any) -> Any:
        if value is None:
            return value

        return self._enum(value)


class CharEnumField(BaseEnumField, pw.CharField):
    def __init__(self, enum: type[StrEnum], **kwargs: Any) -> None:
        super().__init__(enum=enum, **kwargs)


class IntEnumField(BaseEnumField, pw.SmallIntegerField):
    def __init__(self, enum: type[IntEnum], **kwargs: Any) -> None:
        super().__init__(enum=enum, **kwargs)
