import peewee as pw

from miggy.auto import diff_many
from miggy.state import State
from tests.helpers import operation_to_one_line, to_one_line


def test_create_model_w_constraint() -> None:
    class Test(pw.Model):
        first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])
        age = pw.IntegerField()

    diffs = diff_many(State(), State({"test": Test}))
    changes = [operation_to_one_line(o) for o in diffs]
    assert changes == [
        to_one_line(
            """migrator.create_model(
                name='Test',
                fields={
                    'first_name': pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")]),
                    'age': pw.IntegerField(),
                },
                meta={},)"""
        )
    ]


def test_create_model() -> None:
    class Test(pw.Model):
        constraint = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])
        i1 = pw.IntegerField()
        i2 = pw.IntegerField()

        class Meta:
            indexes = ((("i1", "i2"), True),)

    Test.add_index(Test.i1, Test.i2, name="i3")

    changes = diff_many(State(), State({"test": Test}))
    create_model_code = changes[0]

    assert operation_to_one_line(create_model_code) == to_one_line(
        """
            migrator.create_model(
                name='Test',
                fields={
                    'constraint': pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")]),
                    'i1': pw.IntegerField(),
                    'i2': pw.IntegerField(),},
                meta={},
        )
        """
    )
    assert operation_to_one_line(changes[1]) == "migrator.add_index('test','i1','i2',name='test_i1_i2',unique=True,)"
    assert operation_to_one_line(changes[2]) == "migrator.add_index('test','i1','i2',name='i3',)"
