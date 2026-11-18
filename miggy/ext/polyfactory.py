"""Polyfactory-based factories for peewee models.

An analog of :mod:`polyfactory.factories.sqlalchemy_factory` for the peewee ORM:
:class:`PeeweeFactory` is a polyfactory ``BaseFactory`` subclass which knows how to
introspect peewee model fields and persist the generated instances.

Example:
    >>> from peewee import Model, CharField
    >>> from miggy.ext.polyfactory import PeeweeFactory
    >>> class Author(Model):
    ...     name = CharField()
    >>> class AuthorFactory(PeeweeFactory[Author]):
    ...     pass
    >>> author = AuthorFactory.create_sync()  # built and saved in one call
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, Generic, TypeVar, Union
from uuid import UUID

import peewee as pw
from playhouse.postgres_ext import BinaryJSONField, DateTimeTZField
from polyfactory.exceptions import ParameterException
from polyfactory.factories.base import BaseFactory
from polyfactory.field_meta import FieldMeta, Null
from polyfactory.persistence import AsyncPersistenceProtocol, SyncPersistenceProtocol
from polyfactory.utils.types import Frozendict

if TYPE_CHECKING:
    from typing import TypeGuard


T = TypeVar("T")


def _collect_unsaved_relations(obj: Any, seen: set[int] | None = None) -> list[Any]:
    """Collect unsaved FK-related instances of ``obj`` in dependency order (children first)."""
    if seen is None:
        seen = set()

    result: list[Any] = []
    for ref in obj._meta.refs:
        related = obj.__rel__.get(ref.name)
        if related is None or related._pk is not None or id(related) in seen:
            continue
        seen.add(id(related))
        result.extend(_collect_unsaved_relations(related, seen))
        result.append(related)
    return result


_PEEWEE_FIELD_PYTHON_TYPES: dict[type, type] = {
    **{
        field_class: python_type
        for name, python_type in (
            ("AutoField", int),
            ("BigAutoField", int),
            ("BlobField", bytes),
            ("BinaryField", bytes),
            ("BooleanField", bool),
            ("CharField", str),
            ("TextField", str),
            ("FixedCharField", str),
            ("DateField", date),
            ("DateTimeField", datetime),
            ("TimestampField", datetime),
            ("TimeField", time),
            ("DecimalField", Decimal),
            ("IPField", str),
            ("UUIDField", UUID),
            ("BinaryUUIDField", UUID),
            ("IntegerField", int),
            ("SmallIntegerField", int),
            ("BigIntegerField", int),
            ("FloatField", float),
            ("DoubleField", float),
            ("BitField", int),
            ("BigBitField", int),
            ("JSONField", dict),
        )
        if (field_class := getattr(pw, name, None)) is not None
    },
    DateTimeTZField: datetime,
    BinaryJSONField: dict,
}


class PeeweeSyncPersistence(SyncPersistenceProtocol[T]):
    def _save(self, m: Any) -> None:
        m.save(force_insert=True)

    def save(self, data: T) -> T:
        for related in _collect_unsaved_relations(data):
            self._save(related)
        self._save(data)
        return data

    def save_many(self, data: list[T]) -> list[T]:
        for related in (rel for item in data for rel in _collect_unsaved_relations(item)):
            self._save(related)
        for item in data:
            self._save(item)
        return data


class PeeweeAsyncPersistence(AsyncPersistenceProtocol[T]):
    async def _save(self, m: Any) -> None:
        await m.asave(force_insert=True)

    async def save(self, data: T) -> T:
        for related in _collect_unsaved_relations(data):
            await self._save(related)
        await self._save(data)
        return data

    async def save_many(self, data: list[T]) -> list[T]:
        for related in (rel for item in data for rel in _collect_unsaved_relations(item)):
            await self._save(related)
        for item in data:
            await self._save(item)
        return data


class PeeweeFactory(BaseFactory[T], Generic[T]):
    """Base factory for Peewee models."""

    __is_base_factory__ = True

    @classmethod
    def is_supported_type(cls, value: Any) -> TypeGuard[type[T]]:
        return isinstance(value, type) and issubclass(value, pw.Model)

    @classmethod
    def _get_sync_persistence(cls) -> SyncPersistenceProtocol[T]:
        return PeeweeSyncPersistence()

    @classmethod
    def _get_async_persistence(cls) -> AsyncPersistenceProtocol[T]:
        return PeeweeAsyncPersistence()

    @staticmethod
    def _get_python_type(field: pw.Field) -> type:
        klass = type(field)
        if klass in _PEEWEE_FIELD_PYTHON_TYPES:
            return _PEEWEE_FIELD_PYTHON_TYPES[klass]
        msg = f"Cannot determine the Python type for field {field.name!r} ({type(field).__name__})"
        raise ParameterException(msg)

    @staticmethod
    def _get_constraints(field: pw.Field) -> dict[str, Any]:
        constraints: dict[str, Any] = {}
        if isinstance(field, pw.CharField) and field.max_length is not None:
            constraints["max_length"] = field.max_length
        if isinstance(field, pw.DecimalField) and field.max_digits is not None and field.decimal_places is not None:
            constraints["max_digits"] = field.max_digits
            constraints["decimal_places"] = field.decimal_places
        return constraints

    @classmethod
    def should_field_be_set(cls, field: pw.Field) -> bool:
        if field.primary_key:
            return False
        if isinstance(field, pw.ManyToManyField):
            return False
        return True

    @classmethod
    def get_type_from_field(cls, field: pw.Field) -> type:
        if isinstance(field, pw.ForeignKeyField):
            annotation: Any = field.rel_model
        elif enum_class := getattr(field, "enum_class", None):
            annotation = enum_class
        else:
            annotation = cls._get_python_type(field)
            if constraints := cls._get_constraints(field):
                annotation = Annotated[annotation, Frozendict(constraints)]  # type: ignore[valid-type]

        if field.null:
            annotation = Union[annotation, None]

        return annotation

    @classmethod
    def get_model_fields(cls) -> list[FieldMeta]:
        return [
            FieldMeta.from_type(
                annotation=cls.get_type_from_field(field),
                name=field.name,
                default=field.default if field.default is not None else Null,
            )
            for field in cls.__model__._meta.fields.values()  # type: ignore[attr-defined]
            if cls.should_field_be_set(field)
        ]
