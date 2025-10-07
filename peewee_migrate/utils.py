from typing import TYPE_CHECKING

import peewee as pw


def exec_in(code, glob, loc=None):
    if isinstance(code, str):
        code = compile(code, "<string>", "exec", dont_inherit=True)
    exec(code, glob, loc)


class Model(pw.Model):
    if TYPE_CHECKING:
        _meta: pw.Metadata


ModelCls = type[Model]
