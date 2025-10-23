import peewee as pw
from playhouse.postgres_ext import (
    ArrayField,
    BinaryJSONField,
    DateTimeTZField,
    HStoreField,
    IntervalField,
    JSONField,
    TSVectorField,
)

from peewee_migrate.auto import create_model, diff_many, model_to_code


def test_create_model_w_constraint() -> None:
    class Test(pw.Model):
        first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])

    code = diff_many([Test], [])[0]
    assert code == create_model(Test)
    assert """first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")], max_length=255)""" in code


def test_auto_postgresext():
    class Object(pw.Model):
        array_field = ArrayField()
        binary_json_field = BinaryJSONField()
        dattime_tz_field = DateTimeTZField()
        hstore_field = HStoreField()
        interval_field = IntervalField()
        json_field = JSONField()
        ts_vector_field = TSVectorField()

    code = model_to_code(Object)
    assert code
    assert "json_field = pw_pext.JSONField()" in code
    assert "hstore_field = pw_pext.HStoreField(index=True)" in code
