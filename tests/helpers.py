from enum import IntEnum
from textwrap import dedent

from miggy.ext.utils import StrEnum


def to_one_line(s):
    return "".join(line.strip() for line in s.splitlines())


class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Rating(IntEnum):
    LOW = 1
    MIDDLE = 2
    HIGH = 3


def compare_dedent(s1: str, s2: str) -> None:
    assert dedent(s1).strip() == dedent(s2).strip()
