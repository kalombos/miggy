import peewee as pw

from miggy.state import State


def test_add_model() -> None:
    state = State()
    state.add_model(
        "User",
        {
            "age": pw.IntegerField(),
            "email": pw.CharField(max_length=255, null=True),
        },
        {"table_name": "users"},
    )
    model = state["user"]

    assert model.__name__ == "User"
    assert model._meta.table_name == "users"

    assert model.email.max_length == 255
    assert model.email.null is True
    assert isinstance(model.email, pw.CharField)

    assert isinstance(model.age, pw.IntegerField)


def test_remove_model() -> None:
    state = State()
    state.add_model(
        "User",
        {
            "age": pw.IntegerField(),
            "email": pw.CharField(max_length=255, null=True),
        },
        {"table_name": "users"},
    )

    state.remove_model("user")

    assert "user" not in state


def test_add_fields() -> None:
    class User(pw.Model):
        test = pw.CharField()

    state = State()

    state["user"] = User
    state.add_fields(
        "User",
        age=pw.IntegerField(),
        email=pw.CharField(max_length=255, null=True),
    )
    model = state["user"]

    assert model.email.max_length == 255
    assert model.email.null is True
    assert isinstance(model.email, pw.CharField)
    assert isinstance(model.age, pw.IntegerField)
