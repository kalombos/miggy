from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any

import peewee as pw

from miggy.types import ModelCls

if TYPE_CHECKING:
    from collections.abc import Sequence

    from miggy.types import ModelCls


def exec_in(code, glob, loc=None):
    if isinstance(code, str):
        code = compile(code, "<string>", "exec", dont_inherit=True)
    exec(code, glob, loc)


class Default(pw.ColumnBase):
    def __init__(self, value: str) -> None:
        self.value = value

    def __sql__(self, ctx) -> Any:
        ctx.literal("DEFAULT (%s)" % self.value)
        return ctx

    @classmethod
    def from_SQL(cls, sql: pw.SQL) -> None | Default:
        """
        Parse the constraint from raw sql
        """
        _sql = sql.sql.strip()
        if sql.params or not _sql.lower().startswith("default "):
            return None
        value = _sql.split(maxsplit=1)[1]
        if not value.strip():
            return None
        return Default(value=_sql.split(maxsplit=1)[1])


def get_default_constraint(field: pw.Field) -> None | Default:
    if field.constraints is None:
        return None
    constraints = []
    for constraint in field.constraints:
        if isinstance(constraint, Default):
            constraints.append(constraint)
        elif isinstance(constraint, pw.SQL):
            if _constraint := Default.from_SQL(constraint):
                constraints.append(_constraint)
    if len(constraints) > 1:
        raise ValueError(f'"{field.name}" field has more than one default constraint')
    return constraints[0] if constraints else None


def get_default_constraint_value(field: pw.Field):
    c = get_default_constraint(field)
    return c.value if c else None


def _truncate_constraint_name(constraint, maxlen=64):
    if len(constraint) > maxlen:
        name_hash = hashlib.md5(constraint.encode("utf-8")).hexdigest()
        constraint = "%s_%s" % (constraint[: (maxlen - 8)], name_hash[:7])
    return constraint


class ModelIndex(pw.ModelIndex):
    def __init__(
        self,
        model: ModelCls,
        fields: Sequence[pw.Field],
        unique: bool = False,
        safe: bool = True,
        where: pw.SQL | None = None,
        concurrently=False,
        using=None,
        name: str | None = None,
    ) -> None:
        self.concurrently = concurrently
        super().__init__(model=model, fields=fields, unique=unique, safe=safe, where=where, using=using, name=name)

    def _generate_name_from_fields(self, model, fields):
        accum = [field.column_name for field in fields]

        if not accum:
            raise ValueError("Unable to generate a name for the index, please explicitly specify a name.")

        clean_field_names = re.sub(r"[^\w]+", "", "_".join(accum))
        prefix = model._meta.table_name
        return _truncate_constraint_name("_".join((prefix, clean_field_names)))

    def __sql__(self, ctx):
        context = super().__sql__(ctx)
        if self.concurrently:
            context._sql.insert(1, "CONCURRENTLY ")
        return context


def has_single_index(field: pw.Field) -> bool:
    return field.index or field.unique


def make_single_index(field: pw.Field) -> ModelIndex:
    return ModelIndex(field.model, (field,), unique=field.unique, safe=False, using=field.index_type)


def get_single_index_name(field: pw.Field) -> str:
    return make_single_index(field)._name


def get_single_index(field: pw.Field) -> pw.Model:
    if has_single_index(field):
        return make_single_index(field)
    return None


def indexes_state(model_cls: pw.Model) -> dict[str, ModelIndex]:
    if not hasattr(model_cls._meta, "indexes_state"):
        model_cls._meta.indexes_state = {}
    return model_cls._meta.indexes_state


def copy_model(model_cls: ModelCls) -> ModelCls:
    # this function based on ModelBase.__new__ logic
    attrs = {}
    # copying fields
    for k, v in model_cls.__dict__.items():
        if isinstance(v, pw.FieldAccessor):
            attrs[k] = deepcopy(v.field)
    # copying Meta
    meta_options = {}
    if hasattr(model_cls, "_meta"):
        base_meta = model_cls._meta
        meta_keys = ["legacy_table_names", "table_name", "database", "indexes_state"]
        for k in meta_keys:
            try:
                meta_options[k] = base_meta.__dict__[k]
            except KeyError:
                pass
        attrs["Meta"] = type("Meta", (object,), meta_options)
    return type(model_cls.__name__, model_cls.__bases__, attrs)


def delete_field(model: ModelCls, field: pw.Field) -> None:
    """Delete field from model."""
    model._meta.remove_field(field.name)
    delattr(model, field.name)
    if isinstance(field, pw.ForeignKeyField):
        delattr(model, field.object_id_name)
        delattr(field.rel_model, field.backref)
