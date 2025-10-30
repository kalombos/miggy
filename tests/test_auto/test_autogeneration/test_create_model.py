import peewee as pw

from miggy.auto import create_model, diff_many


def test_create_model_w_constraint() -> None:
    class Test(pw.Model):
        first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")])

    code = diff_many([Test], [])[0]
    assert code == create_model(Test)
    assert """first_name = pw.CharField(constraints=[pw.SQL("DEFAULT 'music'")], max_length=255)""" in code
