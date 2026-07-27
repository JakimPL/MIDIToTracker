from enum import StrEnum, unique


@unique
class TrackerFormat(StrEnum):
    """A tracker file format a module can be written as."""

    IT = "it"
    XM = "xm"
