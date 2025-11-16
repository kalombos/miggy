import pytest
from peewee import sort_models

from .models import db
from .utils import list_models


@pytest.fixture(scope="session", autouse=True)
def create_tables() -> None:
    db.create_tables(list_models())


@pytest.fixture(autouse=True)
def clear_tables(create_tables: None):
    for model in reversed(sort_models(list_models())):
        db.execute_sql(
            f'DELETE FROM "{model._meta.table_name}"',
        )
