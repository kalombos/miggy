from __future__ import annotations

from typing import Any

import peewee as pw


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
