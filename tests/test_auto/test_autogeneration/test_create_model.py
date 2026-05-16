import peewee as pw

from miggy.auto import create_model, diff_many
from tests.helpers import operation_to_one_line


def test_create_model_w_constraint() -> None:
    class Test(pw.Model):
        first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])

    code = diff_many([Test], [])[0]
    assert code == create_model(Test)
    assert """first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])""" in code


def test_create_model() -> None:
    class Test(pw.Model):
        constraint = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])
        i1 = pw.IntegerField()
        i2 = pw.IntegerField()

        class Meta:
            indexes = ((("i1", "i2"), True),)

    Test.add_index(Test.i1, Test.i2, name="i3")

    changes = diff_many([Test], [])
    create_model_code = changes[0]

    assert create_model_code == create_model(Test)
    assert operation_to_one_line(changes[1]) == "migrator.add_index('test','i1','i2',name='test_i1_i2',unique=True,)"
    assert operation_to_one_line(changes[2]) == "migrator.add_index('test','i1','i2',name='i3',)"
