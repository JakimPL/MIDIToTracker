from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final

from trackmod.core.instruments.transfer import extract
from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.core.songs.song import Song
from trackmod.trackers.it.module import ITModule
from trackmod.trackers.it.spec.identity import EXTENSION as IT_EXTENSION
from trackmod.trackers.xm.module import XMModule
from trackmod.trackers.xm.spec.identity import EXTENSION as XM_EXTENSION

from midi2tracker.instruments.error import BankError


def _impulse_tracker(path: Path) -> Song:
    return ITModule.load(path).song


def _fast_tracker(path: Path) -> Song:
    return XMModule.load(path).song


READERS: Final[Mapping[str, Callable[[Path], Song]]] = {
    IT_EXTENSION: _impulse_tracker,
    XM_EXTENSION: _fast_tracker,
}


def load_song(path: Path) -> Song:
    """The song held in an instrument file, whichever format wrote it.

    What a bank reads is independent of what a conversion writes, so an Impulse Tracker instrument is
    equally available to a module written as FastTracker 2 — the crossing is the writer's to grade.

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
    song = load_song(path)
    if index >= len(song.instruments):
        raise BankError(f"{path} holds {len(song.instruments)} instrument(s), so {index} names none of them")

    return extract(song, index)
