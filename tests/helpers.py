from enum import IntEnum
from textwrap import dedent

from miggy.auto import MigrationAutodetector
from miggy.ext.utils import StrEnum
from miggy.operations import MigrateOperation
from miggy.state import State
from miggy.types import ModelCls
from miggy.writer import OperationWriter


def get_active_status() -> str:
    return "active"


def get_inactive_status() -> str:
    return "inactive"


def to_one_line(s) -> str:
    return "".join(line.strip() for line in s.splitlines())


def operation_to_one_line(operation: MigrateOperation) -> str:
    return to_one_line(OperationWriter(operation).serialize())


class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Rating(IntEnum):
    LOW = 1
    MIDDLE = 2
    HIGH = 3


def compare_dedent(s1: str, s2: str) -> None:
    assert dedent(s1).strip() == dedent(s2).strip()


def diff_one(prev: ModelCls, current: ModelCls) -> list[MigrateOperation]:
    return MigrationAutodetector(State({"test": prev}), State({"test": current})).diff_one("test")
