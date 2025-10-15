from __future__ import annotations

import peewee as pw


class Default(pw.ColumnBase):
    """
    DEFAULT constraint
    """

    def __init__(self, value: str):
        # TODO подумать с типом, можно запутаться и сделать Default("some name") для строки, что приведет к ошибке.
        self.value = value

    def __sql__(self, ctx):
        ctx.literal('DEFAULT (%s)' % self.value)
        return ctx

    @classmethod
    def from_SQL(cls, sql: pw.SQL) -> None | Default:
        """
        Parse the constraint from raw sql
        """
        _sql = sql.sql.strip()
        if sql.params or not _sql.lower().startswith("default "):
            return None
        return Default(
            value=_sql.split(maxsplit=1)[1]
        )
