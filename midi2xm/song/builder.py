"""Assembling one parsed MIDI file into the song a tracker module is written from.

This is where the conversion's choices meet: the row rate and speed fix the grid, the channel count fixes
the polyphony, and the instrument slot fixes which of the module's instruments the notes name. What comes
out is a format-agnostic song, so binding it to a file format is a separate, later step.

The song runs a beat past its last release, so the final note has room to ring rather than being cut off
by the module looping back to the start.
"""

from __future__ import annotations

from dataclasses import dataclass

from trackmod.core.instruments.instrument import Instrument
from trackmod.core.instruments.keymap import routed_keymap
from trackmod.core.songs.order import OrderList
from trackmod.core.songs.playback import Playback
from trackmod.core.songs.song import Song

from midi2xm.midi.events import MidiSong, TempoEvent
from midi2xm.song.height import pattern_height
from midi2xm.song.instrument import placeholder_instrument, placeholder_sample
from midi2xm.song.layout import Layout
from midi2xm.song.patterns import Grids, build_patterns
from midi2xm.timing.grid import RowGrid
from midi2xm.timing.tempo import playable_tempo
from midi2xm.voices.allocation import Allocation

TRAILING_BEATS = 1  # how long the song plays on past its last release, so the final note rings


@dataclass(frozen=True)
class Conversion:
    """One converted piece: the song, and everything the conversion had to give up on the way."""

    song: Song
    stolen_notes: int
    dropped_tempos: tuple[TempoEvent, ...]

    @property
    def rows(self) -> int:
        """How many rows the song plays through."""
        return self.song.rows


def _instruments(slot: int) -> tuple[Instrument, ...]:
    """The instrument list, with the played one in ``slot`` and empty slots reserved before it.

    A tracker names instruments by position, so putting the notes on a chosen slot means the slots below
    it exist and hold nothing — which is exactly what an empty keymap is.
    """
    silent = Instrument(name="", keymap=routed_keymap({}))
    return (*(silent for _ in range(slot)), placeholder_instrument())


def _channels_used(allocation: Allocation) -> int:
    """How many channels the module declares: the ones reached, rounded up to a pair.

    Tracker channels are laid out in stereo pairs, so an odd count leaves a half-populated pair that some
    players and editors handle poorly.
    """
    return allocation.channels + allocation.channels % 2


def build_song(midi: MidiSong, allocation: Allocation, grid: RowGrid, layout: Layout) -> Conversion:
    """The song a MIDI file becomes: its voices on channels, its tempo changes as effects."""
    rows = grid.row_of(midi.last_tick) + grid.rows_per_beat * TRAILING_BEATS + 1
    channels = _channels_used(allocation)
    grids = Grids.covering(rows, channels=channels, height=pattern_height(rows, preferred=layout.height))
    written = build_patterns(grids, allocation, midi.tempos, grid, instrument=layout.slot)
    song = Song(
        name=layout.name,
        channels=channels,
        patterns=written.patterns,
        order=OrderList.sequential(len(written.patterns)),
        instruments=_instruments(layout.slot),
        samples=(placeholder_sample(),),
        playback=Playback(
            speed=grid.speed,
            tempo=playable_tempo(midi.tempos[0].beats_per_minute, speed=grid.speed, rows_per_beat=grid.rows_per_beat),
        ),
    )
    return Conversion(song=song, stolen_notes=allocation.stolen, dropped_tempos=written.dropped_tempos)
