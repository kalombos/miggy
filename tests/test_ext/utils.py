import inspect

import peewee as pw

from . import models


def list_models() -> list:
    return [m for _, m in inspect.getmembers(models, inspect.isclass) if issubclass(m, pw.Model)]
