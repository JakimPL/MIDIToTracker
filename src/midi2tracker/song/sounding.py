from __future__ import annotations

from dataclasses import dataclass

from midi2tracker.instruments.bank import Voicing
from midi2tracker.instruments.ensemble import Ensemble
from midi2tracker.instruments.expression import Expression
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

    What went unheard is kept as the voices themselves, so each one still names the track it was read
    from and the caller sees which stem, and so which instrument, to correct.
    """

    sounded: tuple[Sounded, ...]
    unplayable: tuple[Voice, ...]
    silent: tuple[Voice, ...]


def sound(allocation: Allocation, *, ensemble: Ensemble, target: TrackerTarget) -> Sounding:
    """Which of a piece's voices the module states, and on what.

    A voice carries the track it came from, so the bank that answers it is the one that track plays
    through.
    """
    sounded: list[Sounded] = []
    unplayable: list[Voice] = []
    silent: list[Voice] = []
    for voice in allocation.voices:
        if not target.carries(voice.note.pitch):
            unplayable.append(voice)
            continue

        voicing = ensemble.voicing(voice.track, target.key(voice.note.pitch), Expression.of(voice.note))
        if voicing is None:
            silent.append(voice)
            continue

        sounded.append(Sounded(voice=voice, voicing=voicing))

    return Sounding(
        sounded=tuple(sounded),
        unplayable=tuple(unplayable),
        silent=tuple(silent),
    )
