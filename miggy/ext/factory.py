import collections
import datetime as dt
import random
from collections.abc import Callable
from typing import Any

import peewee as pw
from playhouse.postgres_ext import BinaryJSONField, DateTimeTZField

from miggy.ext.fields import CharEnumField, IntEnumField


class Counter(collections.Counter):
    def inc(self, element: str) -> int:
        self.update(**{element: 1})
        return self[element]


counter = Counter()


def char_enum_field_factory(field: pw.Field) -> str:
    first_choice = field.choices[0]
    first_value: str = first_choice[0]
    return first_value


def char_field_factory(field: pw.Field) -> str:
    value = counter.inc(field.name)
    return "%s%s" % (field.name, value)


def integer_field_factory(field: pw.Field) -> int:
    return counter.inc(field.name)


def json_field_factory(field: pw.Field) -> dict[str, Any]:
    value = counter.inc(field.name)
    return {f"key{value}": f"value{value}"}


field_type_map = {
    pw.DateField: lambda _: dt.date.today(),  # noqa: DTZ011
    pw.DateTimeField: lambda _: dt.datetime.now(),  # noqa: DTZ005
    DateTimeTZField: lambda _: dt.datetime.now(tz=dt.timezone.utc),
    pw.CharField: char_field_factory,
    pw.TextField: char_field_factory,
    pw.IntegerField: integer_field_factory,
    pw.SmallIntegerField: integer_field_factory,
    pw.BooleanField: lambda _: False,
    pw.BigIntegerField: lambda _: random.randint(1, 9999999),
    BinaryJSONField: json_field_factory,
    CharEnumField: lambda f: list(f._enum)[0].value,
    IntEnumField: lambda f: list(f._enum)[0].value,
}

_missing = object()


class FieldNotFound(Exception):
    pass


FieldMap = dict[type[pw.Field], Callable[[pw.Field], Any]]


def model_factory(
    model: type[pw.Model],
    custom_field_type_map: FieldMap | None = None,
    fill_nullable_values: bool = False,
    **kwargs: Any,
) -> pw.Model:
    """
    Create and save an instance of a Peewee model, automatically populating
    all required fields.

    Parameters
    ----------
    model : type[pw.Model]
        The Peewee model class to instantiate.
    custom_field_type_map : FieldMap | None, optional
        A mapping that allows customizing factory functions for specific
        field types. If ``None``, default handlers are used.
    fill_nullable_values : bool, optional
        Whether to automatically fill nullable fields as well.
    \*\*kwargs : Any
        ``field_name=value`` pairs that override or provide values for particular
        model fields.

    Returns
    -------
    pw.Model
        The newly created and saved model instance.

    Example
    -------
    >>> book = model_factory(Book, name="mytestname")
    """
    _field_type_map = field_type_map.copy()
    if custom_field_type_map is not None:
        _field_type_map.update(custom_field_type_map)

    nm = model()
    for field_name in kwargs:
        if field_name not in model._meta.fields:
            raise FieldNotFound(f'{model.__name__} has no "{field_name}" field')
    for field in model._meta.fields.values():
        field_name = field.name
        field_type = type(field)
        field_value = kwargs.get(field_name, _missing)
        if field_value is not _missing:
            pass
        elif field.primary_key or field.default is not None:
            continue
        elif field.null and not fill_nullable_values:
            field_value = None
        elif field_type is pw.ForeignKeyField:
            field_value = model_factory(
                field.rel_model, custom_field_type_map=_field_type_map, fill_nullable_values=fill_nullable_values
            )
        else:
            field_factory = _field_type_map[field_type]
            field_value = field_factory(field)
        setattr(nm, field_name, field_value)
    nm.save(force_insert=True)
    return nm
