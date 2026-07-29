from __future__ import annotations

from dataclasses import dataclass

from midi2tracker.arrangement.mode import ChannelAllocation
from midi2tracker.arrangement.track import Track
from midi2tracker.instruments.ensemble import Ensemble
from midi2tracker.midi.events import MidiSong, TempoEvent


@dataclass(frozen=True)
class UnheardTempo:
    """A tempo one track states that the piece does not follow, and the track that stated it."""

    track: str
    tempo: TempoEvent


@dataclass(frozen=True)
class Arrangement:
    """Several MIDI files as one piece: their tracks, the instrument table, and the clock they follow.

    Every track counts its ticks in the same resolution, so the tracks are read against one grid.
    ``timekeeper`` is the track whose tempo map the module states, since a module keeps one clock.
    """

    name: str
    tracks: tuple[Track, ...]
    ensemble: Ensemble
    timekeeper: int
    allocation: ChannelAllocation

    @property
    def timing(self) -> MidiSong:
        """The track the piece follows the tempo of, which is what the row grid is built from."""
        return self.tracks[self.timekeeper].midi

    @property
    def pulses_per_beat(self) -> int:
        """The resolution every track counts its ticks in."""
        return self.timing.pulses_per_beat

    @property
    def tempos(self) -> tuple[TempoEvent, ...]:
        """The tempo map the module plays, which is the timekeeping track's own."""
        return self.timing.tempos

    @property
    def fastest(self) -> float:
        """The highest tempo the piece reaches, which is what the row clock has to keep up with."""
        return self.timing.fastest

    @property
    def last_tick(self) -> int:
        """The tick the piece stops on: the last release of any of its tracks."""
        return max(track.midi.last_tick for track in self.tracks)

    @property
    def notes(self) -> int:
        """How many notes the whole piece plays."""
        return sum(len(track.midi.notes) for track in self.tracks)

    @property
    def unheard_tempos(self) -> tuple[UnheardTempo, ...]:
        """Every tempo a track states that the piece does not follow.

        A module keeps one clock, so one track's tempo map is the piece's and the others' are read for
        their notes alone. Naming what went unheard is what lets a caller point ``clock`` at the track
        whose timing the piece should have followed. A track agreeing with the clock states nothing here.
        """
        heard = frozenset(self.tempos)
        return tuple(
            UnheardTempo(track=track.name, tempo=tempo)
            for index, track in enumerate(self.tracks)
            if index != self.timekeeper
            for tempo in track.midi.tempos
            if tempo not in heard
        )
