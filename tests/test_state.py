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
    class RelatedModel(pw.Model):
        f = pw.CharField()

    class User(pw.Model):
        test = pw.CharField()

    state = State({"user": User, "relatedmodel": RelatedModel})

    state.add_fields(
        "User",
        age=pw.IntegerField(),
        email=pw.CharField(max_length=255, null=True),
        related_field=pw.ForeignKeyField("relatedmodel"),
        self_related_field=pw.ForeignKeyField("self"),
    )
    model = state["user"]

    assert model.email.max_length == 255
    assert model.email.null is True
    assert isinstance(model.email, pw.CharField)
    assert isinstance(model.age, pw.IntegerField)

    assert isinstance(model.related_field.rel_model.f, pw.CharField)
    assert isinstance(model.self_related_field.rel_model.age, pw.IntegerField)
