import sys

if sys.version_info < (3, 11):
    from strenum import StrEnum
else:
    from enum import StrEnum  # noqa: F401 
