from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any, NamedTuple

import peewee as pw

from miggy.types import ModelCls

if TYPE_CHECKING:
    from collections.abc import Sequence

    from miggy.types import ModelCls


def exec_in(code, glob, loc=None):
    if isinstance(code, str):
        code = compile(code, "<string>", "exec", dont_inherit=True)
    exec(code, glob, loc)


def node_to_string(node: pw.Node) -> str:
    ctx = pw.Context()
    sql, params = ctx.sql(node).query()

    if not params:
        return sql.strip()
    return ""


class DefaultMeta(NamedTuple):
    value: str

    @classmethod
    def from_node(cls, node: pw.Node) -> None | DefaultMeta:
        sql = node_to_string(node)
        match = re.search(r"^\s*DEFAULT\s+(.+)$", sql, re.I)
        if match:
            return cls(value=match.group(1).strip())
        return None


class CheckMeta(NamedTuple):
    name: str
    constraint: str

    @classmethod
    def from_node(cls, node: pw.Node) -> None | CheckMeta:
        pattern = r'(?:CONSTRAINT\s+["\']?(\w+)["\']?\s+)?CHECK\s*\((.+)\)'
        sql = node_to_string(node)
        match = re.search(pattern, sql, re.I)
        if match:
            name = match.group(1)
            if name is None:
                raise ValueError(
                    f"Unnamed CHECK constraints not supported. Please add a name to the constraint: '{sql}'"
                )
            constraint = match.group(2).strip()
            return CheckMeta(name.strip(), constraint.strip())
        return None


def extract_default_meta(field: pw.Field) -> DefaultMeta | None:
    constraints = field.constraints or []
    result = []
    for constraint in constraints:
        if _constraint := DefaultMeta.from_node(constraint):
            result.append(_constraint)
    if len(result) > 1:
        raise ValueError(f'"{field.name}" field has more than one default constraint')
    return result[0] if result else None


def extract_check_meta(field: pw.Field) -> list[CheckMeta]:
    constraints = field.constraints or []
    result = []
    for constraint in constraints:
        if _constraint := CheckMeta.from_node(constraint):
            result.append(_constraint)
    return sorted(set(result))


def get_default_constraint_value(field: pw.Field) -> str | None:
    if default_meta := extract_default_meta(field):
        return default_meta.value
    return None


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
    return make_single_index(field)._name  # type: ignore[attr-defined]


def get_single_index(field: pw.Field) -> pw.ModelIndex | None:
    if has_single_index(field):
        return make_single_index(field)
    return None


def indexes_state(model_cls: ModelCls) -> dict[str, ModelIndex]:
    if not hasattr(model_cls._meta, "indexes_state"):
        model_cls._meta.indexes_state = {}  # type: ignore[attr-defined]
    return model_cls._meta.indexes_state  # type: ignore[attr-defined]


def copy_field(field: pw.Field) -> pw.Field:
    # workaround for check constraint
    # https://github.com/coleifer/peewee/issues/3067
    if tmp_constraints := field.constraints:
        field.constraints = []
    new_field = deepcopy(field)
    if tmp_constraints:
        field.constraints = tmp_constraints
        new_field.constraints = [c.clone() for c in tmp_constraints]
    return new_field


def copy_model(model_cls: ModelCls) -> ModelCls:
    # this function based on ModelBase.__new__ logic
    attrs: dict[str, Any] = {}

    is_pk_already_determined = False
    # copying fields
    for k, v in model_cls.__dict__.items():
        if isinstance(v, pw.FieldAccessor):
            attrs[k] = copy_field(v.field)
            if v.field.primary_key:
                is_pk_already_determined = True
    # copying Meta
    meta_options = {}
    if hasattr(model_cls, "_meta"):
        base_meta = model_cls._meta
        meta_keys = ["legacy_table_names", "table_name", "database", "indexes_state", "primary_key"]
        for k in meta_keys:
            if is_pk_already_determined and k == "primary_key":
                continue
            try:
                meta_options[k] = base_meta.__dict__[k]
            except KeyError:
                pass
        attrs["Meta"] = type("Meta", (object,), meta_options)
    return type(model_cls.__name__, model_cls.__bases__, attrs)


def fk_postfix(name: str) -> str:
    return name if name.endswith("_id") else name + "_id"


def resolve_field(model_cls: ModelCls, field: str) -> pw.Field:
    _field = model_cls._meta.combined.get(field, None)
    if _field is None:
        raise ValueError(f"{model_cls} does not have '{field}' field.")
    return _field
