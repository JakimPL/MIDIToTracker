from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from midi2tracker.arrangement.piece import Arrangement
from midi2tracker.midi.events import NoteEvent
from midi2tracker.song.sounding import Sounding
from midi2tracker.voices.allocation import Allocation
from midi2tracker.voices.voice import Voice


@dataclass(frozen=True)
class TrackReport:
    """What one track of a piece reached, and every note of it the module leaves out.

    A piece assembled from stems is corrected stem by stem: raising a ceiling answers the displaced
    voices of one track, sampling more widely answers the silent notes of one instrument, and a format
    reaching further answers the pitches one part plays. So each count is kept under the track that
    earned it.
    """

    name: str
    notes: int
    channels: int
    stolen: int
    unplayable: tuple[NoteEvent, ...]
    silent: tuple[NoteEvent, ...]

    @property
    def left_out(self) -> int:
        """How many of this track's notes the module states nothing for."""
        return len(self.unplayable) + len(self.silent)


def _read_from(voices: Sequence[Voice], track: int) -> tuple[NoteEvent, ...]:
    """The notes of one track among voices gathered over the whole piece."""
    return tuple(voice.note for voice in voices if voice.track == track)


def report(arrangement: Arrangement, allocation: Allocation, sounding: Sounding) -> tuple[TrackReport, ...]:
    """One report per track, in the order the arrangement states them.

    The three passes each know part of what a track cost — the arrangement how much it plays, the
    allocation how wide it spread, the sounding what the bank and the keyboard answered — and this is
    where they meet as one account per track.
    """
    return tuple(
        TrackReport(
            name=track.name,
            notes=len(track.midi.notes),
            channels=placed.channels,
            stolen=placed.stolen,
            unplayable=_read_from(sounding.unplayable, index),
            silent=_read_from(sounding.silent, index),
        )
        for index, (track, placed) in enumerate(zip(arrangement.tracks, allocation.tracks, strict=True))
    )
