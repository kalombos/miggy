from typing import TYPE_CHECKING, Any

import peewee as pw

if TYPE_CHECKING:
    from collections.abc import Sequence


class Model(pw.Model):
    if TYPE_CHECKING:
        _meta: pw.Metadata


ModelCls = type[Model]


class ModelIndex(pw.ModelIndex):
    if TYPE_CHECKING:
        _expressions: Sequence[Any]
        _name: str
        _unique: bool
        _where: Any
