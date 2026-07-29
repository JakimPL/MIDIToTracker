from __future__ import annotations

from pathlib import Path

from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.trackers.registry import EXTENSIONS
from trackmod.trackers.registry import parse_units as parse_container
from trackmod.trackers.registry import reads

from midi2tracker.instruments.error import BankError


def parse_units(data: bytes, *, extension: str, origin: str) -> tuple[InstrumentUnit, ...]:
    """Every instrument stored bytes hold, in the order they store them.

    A module carries as many as it was written with and a standalone instrument file carries one, so both
    answer the same question and a layer names its instrument the same way whichever it points at. What a
    bank reads is independent of what a conversion writes, so an Impulse Tracker instrument is equally
    available to a module written as FastTracker 2 — the crossing is the writer's to grade.

    ``origin`` names where the bytes came from, so a bank reports the entry a caller can go and look at.

    Raises:
        BankError: when the extension names no format a bank reads, or the bytes read as another one.
    """
    if not reads(extension):
        understood = ", ".join(sorted(EXTENSIONS))
        raise BankError(f"{origin} carries no extension a bank reads; {understood} are what it understands")

    try:
        return parse_container(data, extension=extension)
    except ValueError as unreadable:
        raise BankError(f"{origin} does not read as an instrument file: {unreadable}") from unreadable


def read_units(path: Path) -> tuple[InstrumentUnit, ...]:
    """Every instrument a file on disk holds, which is how a bank of one stated instrument reads it.

    Raises:
        BankError: when the file cannot be read, carries no extension a bank reads, or holds another format.
    """
    try:
        data = path.read_bytes()
    except OSError as unreadable:
        raise BankError(f"{path} does not read as an instrument file: {unreadable}") from unreadable

    return parse_units(data, extension=path.suffix, origin=str(path))


def select_unit(units: tuple[InstrumentUnit, ...], index: int, *, origin: str) -> InstrumentUnit:
    """The instrument at ``index`` of what one file holds, together with the samples its keymap reaches.

    Raises:
        BankError: when the file holds no instrument at that position.
    """
    if index >= len(units):
        raise BankError(f"{origin} holds {len(units)} instrument(s), so {index} names none of them")

    return units[index]
