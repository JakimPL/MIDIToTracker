from __future__ import annotations

from dataclasses import dataclass

from midi2tracker.instruments.bank import Bank
from midi2tracker.midi.events import MidiSong


@dataclass(frozen=True)
class Track:
    """One MIDI file of an arrangement: what it plays, what it plays through, and how wide it may spread.

    ``midi`` is already counted in the arrangement's own resolution, so every track of a piece states its
    ticks on one scale and a row means the same thing to all of them.

    ``channels`` is the ceiling this track allocates within, which the document states per track and the
    settings state for the rest.
    """

    name: str
    midi: MidiSong
    bank: Bank
    channels: int
