import pytest

from miggy.serializer import serialize_value
from tests.helpers import Rating, Status


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5, 5),
        ("5", "5"),
        (Status.ACTIVE, "'active'"),
        (Rating.LOW, "1"),
    ],
)
def test_base_serializer(value: int | str, expected: str) -> None:
    assert serialize_value(value) == expected
