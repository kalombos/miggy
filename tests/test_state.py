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


def test_add_field() -> None:

    class User(pw.Model):
        test = pw.CharField()

    state = State({"user": User})

    state.add_field(
        "User",
        name="email",
        field=pw.CharField(max_length=255, null=True),
    )
    model = state["user"]

    assert model.email.max_length == 255
    assert model.email.null is True
    assert isinstance(model.email, pw.CharField)


def test_add_field__fk() -> None:
    class RelatedModel(pw.Model):
        f = pw.CharField()

    class User(pw.Model):
        test = pw.CharField()

    state = State({"user": User, "relatedmodel": RelatedModel})

    state.add_field(
        "User",
        name="related_field",
        field=pw.ForeignKeyField("relatedmodel"),
    )
    state.add_field(
        "User",
        name="self_related_field",
        field=pw.ForeignKeyField("self"),
    )
    model = state["user"]

    assert isinstance(model.related_field.rel_model.f, pw.CharField)
    assert isinstance(model.self_related_field.rel_model.test, pw.CharField)


def test_remove_field() -> None:
    class SomeModel(pw.Model):
        some_field = pw.CharField()

    class User(pw.Model):
        my_pk = pw.CharField(primary_key=True)
        fk = pw.ForeignKeyField(SomeModel, backref="users")

    state = State({"user": User, "somemodel": SomeModel})

    state.remove_field("User", "my_pk")
    state.remove_field("User", "fk")

    assert not hasattr(SomeModel, "users")
    assert not hasattr(User, "my_pk")
    assert not hasattr(User, "fk_id")
