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
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Generic, TypeVar, Union
from uuid import UUID

import peewee as pw
from playhouse.postgres_ext import BinaryJSONField, DateTimeTZField
from polyfactory.exceptions import ParameterException
from polyfactory.factories.base import BaseFactory
from polyfactory.field_meta import FieldMeta, Null
from polyfactory.persistence import AsyncPersistenceProtocol, SyncPersistenceProtocol
from polyfactory.utils.types import Frozendict

if TYPE_CHECKING:
    from enum import Enum
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


# Python type mapping for peewee 4+, where `Field.field_type` holds the SQL type
# instead of the Python type. Built defensively so that classes that only exist
# in one of the supported peewee versions are skipped.
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

# Relation fields that are left untouched for now (peewee 4+ only).
_SKIP_FIELD_TYPES: tuple[type, ...] = tuple(
    field_class
    for field_class in (getattr(pw, "ManyToManyField", None), getattr(pw, "VirtualField", None))
    if field_class is not None
)


class PeeweeSyncPersistence(SyncPersistenceProtocol[Any]):
    """Sync persistence handler for :class:`PeeweeFactory`."""

    def __init__(self, force_insert: bool = True) -> None:
        self.force_insert = force_insert

    def save(self, data: Any) -> Any:
        for related in _collect_unsaved_relations(data):
            related.save(force_insert=self.force_insert)
        data.save(force_insert=self.force_insert)
        return data

    def save_many(self, data: list[Any]) -> list[Any]:
        for related in (rel for item in data for rel in _collect_unsaved_relations(item)):
            related.save(force_insert=self.force_insert)
        for item in data:
            item.save(force_insert=self.force_insert)
        return data


class PeeweeAsyncPersistence(AsyncPersistenceProtocol[Any]):
    """Async persistence handler for :class:`PeeweeFactory`.

    Relies on ``playhouse.pwasyncio``: the model must derive from
    ``AsyncModel`` and be bound to a database mixing in ``AsyncDatabaseMixin``.
    """

    def __init__(self, force_insert: bool = True) -> None:
        self.force_insert = force_insert

    @staticmethod
    def _check_async_model(data: Any) -> None:
        if not hasattr(type(data), "asave"):
            msg = (
                f"{type(data).__name__} is not an AsyncModel and cannot be persisted asynchronously. "
                "Derive it from `playhouse.pwasyncio.AsyncModel` and bind it to an "
                "`AsyncDatabaseMixin` database."
            )
            raise ParameterException(msg)

    async def save(self, data: Any) -> Any:
        self._check_async_model(data)
        for related in _collect_unsaved_relations(data):
            self._check_async_model(related)
            await related.asave(force_insert=self.force_insert)
        await data.asave(force_insert=self.force_insert)
        return data

    async def save_many(self, data: list[Any]) -> list[Any]:
        for item in data:
            self._check_async_model(item)
        for related in (rel for item in data for rel in _collect_unsaved_relations(item)):
            self._check_async_model(related)
            await related.asave(force_insert=self.force_insert)
        for item in data:
            await item.asave(force_insert=self.force_insert)
        return data


class PeeweeFactory(BaseFactory[T], Generic[T]):
    """Base factory for peewee models, an analog of polyfactory's ``SQLAlchemyFactory``."""

    __is_base_factory__ = True

    __skip_primary_keys__: ClassVar[bool] = True
    """Configuration to skip primary key fields and let the database assign them."""
    __force_insert__: ClassVar[bool] = True
    """Configuration to pass ``force_insert=True`` to ``Model.save()``."""

    __config_keys__ = (
        *BaseFactory.__config_keys__,
        "__skip_primary_keys__",
        "__force_insert__",
    )

    @classmethod
    def is_supported_type(cls, value: Any) -> TypeGuard[type[T]]:
        return isinstance(value, type) and issubclass(value, pw.Model)

    @classmethod
    def _get_sync_persistence(cls) -> SyncPersistenceProtocol[T]:
        return PeeweeSyncPersistence(force_insert=cls.__force_insert__)

    @classmethod
    def _get_async_persistence(cls) -> AsyncPersistenceProtocol[T]:
        return PeeweeAsyncPersistence(force_insert=cls.__force_insert__)

    @staticmethod
    def _get_python_type(field: pw.Field) -> type:
        field_type = getattr(field, "field_type", None)
        if isinstance(field_type, type):
            # peewee < 4: `field_type` holds the Python type
            return field_type
        for klass in type(field).__mro__:
            if klass in _PEEWEE_FIELD_PYTHON_TYPES:
                return _PEEWEE_FIELD_PYTHON_TYPES[klass]
        msg = f"Cannot determine the Python type for field {field.name!r} ({type(field).__name__})"
        raise ParameterException(msg)

    @staticmethod
    def _get_enum_class(field: pw.Field) -> type[Enum] | None:
        for attr in ("enum_class", "_enum"):
            if enum_class := getattr(field, attr, None):
                return enum_class
        return None

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
    def should_set_field(cls, field: pw.Field) -> bool:
        if getattr(field, "_hidden", False):
            return False
        if field.primary_key and cls.__skip_primary_keys__:
            return False
        # Relations are handled separately: FKs are built as related models,
        # while many-to-many and virtual fields are left untouched for now.
        if _SKIP_FIELD_TYPES and isinstance(field, _SKIP_FIELD_TYPES):
            return False
        return True

    @classmethod
    def get_type_from_field(cls, field: pw.Field) -> type:
        if isinstance(field, pw.ForeignKeyField):
            annotation: Any = field.rel_model
        elif enum_class := cls._get_enum_class(field):
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
            if cls.should_set_field(field)
        ]
