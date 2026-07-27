from __future__ import annotations

from dataclasses import dataclass

from midi2tracker.instruments.bank import Bank, Voicing
from midi2tracker.instruments.expression import Expression
from midi2tracker.midi.events import NoteEvent
from midi2tracker.tracker.target import TrackerTarget
from midi2tracker.voices.allocation import Allocation
from midi2tracker.voices.voice import Voice


@dataclass(frozen=True)
class Sounded:
    """One voice the module states, with the slot and volume the bank gives it."""

    voice: Voice
    voicing: Voicing


@dataclass(frozen=True)
class Sounding:
    """What the keyboard and the bank make of a piece's voices, before any of it reaches a grid.

    Two different things leave a note out, and a run says which happened: the format numbers no key for
    its pitch, or the bank routes that key to nothing. Both are the caller's to act on — one by writing
    the piece as a format reaching further, the other by sampling the instrument more widely.
    """

    sounded: tuple[Sounded, ...]
    unplayable: tuple[NoteEvent, ...]
    silent: tuple[NoteEvent, ...]


def sound(allocation: Allocation, *, bank: Bank, target: TrackerTarget) -> Sounding:
    """Which of a piece's voices the module states, and on what."""
    sounded: list[Sounded] = []
    unplayable: list[NoteEvent] = []
    silent: list[NoteEvent] = []
    for voice in allocation.voices:
        if not target.carries(voice.note.pitch):
            unplayable.append(voice.note)
            continue

        voicing = bank.voicing(target.key(voice.note.pitch), Expression.of(voice.note))
        if voicing is None:
            silent.append(voice.note)
            continue

        sounded.append(Sounded(voice=voice, voicing=voicing))

    return Sounding(
        sounded=tuple(sounded),
        unplayable=tuple(unplayable),
        silent=tuple(silent),
    )
