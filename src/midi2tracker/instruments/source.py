from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

from trackmod.core.instruments.transfer import extract
from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.core.songs.song import Song
from trackmod.trackers.it.instrument_file import ITInstrumentFile
from trackmod.trackers.it.module import ITModule
from trackmod.trackers.it.spec.identity import EXTENSION as IT_EXTENSION
from trackmod.trackers.it.spec.identity import INSTRUMENT_EXTENSION as ITI_EXTENSION
from trackmod.trackers.xm.instrument_file import XMInstrumentFile
from trackmod.trackers.xm.module import XMModule
from trackmod.trackers.xm.spec.identity import EXTENSION as XM_EXTENSION
from trackmod.trackers.xm.spec.identity import INSTRUMENT_EXTENSION as XI_EXTENSION

from midi2tracker.instruments.error import BankError


def _held(song: Song) -> tuple[InstrumentUnit, ...]:
    """Every instrument a module holds, each with the samples its own keymap reaches."""
    return tuple(extract(song, index) for index in range(len(song.instruments)))


def _impulse_tracker_module(path: Path) -> tuple[InstrumentUnit, ...]:
    return _held(ITModule.load(path).song)


def _fast_tracker_module(path: Path) -> tuple[InstrumentUnit, ...]:
    return _held(XMModule.load(path).song)


def _impulse_tracker_instrument(path: Path) -> tuple[InstrumentUnit, ...]:
    return (ITInstrumentFile.load(path).unit,)


def _fast_tracker_instrument(path: Path) -> tuple[InstrumentUnit, ...]:
    return (XMInstrumentFile.load(path).unit,)


READERS: Final[Mapping[str, Callable[[Path], tuple[InstrumentUnit, ...]]]] = {
    IT_EXTENSION: _impulse_tracker_module,
    XM_EXTENSION: _fast_tracker_module,
    ITI_EXTENSION: _impulse_tracker_instrument,
    XI_EXTENSION: _fast_tracker_instrument,
}


def read_units(path: Path) -> tuple[InstrumentUnit, ...]:
    """The instruments a file holds, in the order it stores them.

    A module carries as many as it was written with and a standalone instrument file carries one, so both
    answer the same question and a layer names its instrument the same way whichever it points at. What a
    bank reads is independent of what a conversion writes, so an Impulse Tracker instrument is equally
    available to a module written as FastTracker 2 — the crossing is the writer's to grade.

    Raises:
        BankError: when the suffix names no reader, or the file reads as something else.
    """
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        understood = ", ".join(sorted(READERS))
        raise BankError(f"{path} carries no extension a bank reads; {understood} are what it understands")

    try:
        return reader(path)
    except (OSError, ValueError) as unreadable:
        raise BankError(f"{path} does not read as an instrument file: {unreadable}") from unreadable


def load_unit(path: Path, index: int) -> InstrumentUnit:
    """The instrument at ``index`` of a file, together with the samples its keymap reaches.

    Raises:
        BankError: when the file cannot be read, or holds no instrument at that position.
    """
    units = read_units(path)
    if index >= len(units):
        raise BankError(f"{path} holds {len(units)} instrument(s), so {index} names none of them")

    return units[index]
