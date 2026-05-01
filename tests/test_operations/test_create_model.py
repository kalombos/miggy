import peewee as pw

from miggy.operations import CreateModel
from miggy.state import State


def test_state_forwards() -> None:

    operation = CreateModel(
        "User", 
        {
            "name": pw.CharField(max_length=100),
            "email": pw.CharField(max_length=255, null=True),
        }, 
        {}
    )
    state = State()
    operation.state_forwards(state)
    model = state["user"]

    assert model.__name__ == "User"
    assert isinstance(model.email, pw.CharField)
    assert isinstance(model.name, pw.CharField)
