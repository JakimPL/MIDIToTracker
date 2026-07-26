"""Writing the allocated voices onto the pattern grids a tracker reads.

The grid is one continuous run of rows cut into patterns of a fixed height, so a row's address is a
pattern and an offset within it. Three passes fill it, in an order that decides what wins where they meet:
notes first, then the key-offs that end them, then the tempo changes.

Key-offs give way to notes because a row that both releases one voice and starts another on the same
channel can only say one thing, and the note is what the listener hears — the released voice ends when the
new one takes the channel anyway. Tempo changes belong to the row rather than to a voice, so they go into
whichever channel still has a free effect column; a row where every channel already carries an effect has
nowhere to put one, which is reported rather than passed over.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from trackmod.core.notes.command import NoteCommand
from trackmod.core.patterns.builder import PatternBuilder
from trackmod.core.patterns.cell import Cell
from trackmod.core.patterns.grid import Pattern
from trackmod.xm.effects.catalog import XM_EFFECTS

from midi2xm.midi.events import TempoEvent
from midi2xm.song.mapping import tracker_note, tracker_volume
from midi2xm.timing.grid import RowGrid
from midi2xm.timing.tempo import playable_tempo
from midi2xm.voices.allocation import Allocation
from midi2xm.voices.voice import Voice


@dataclass(frozen=True)
class Grids:
    """The pattern builders of one song, addressed by absolute row.

    Holding them behind one address space is what lets the passes work in the song's own rows rather than
    each translating a pattern and an offset for itself.
    """

    builders: tuple[PatternBuilder, ...]
    height: int

    @classmethod
    def covering(cls, rows: int, *, channels: int, height: int) -> Grids:
        """Enough patterns of ``height`` rows to hold ``rows`` rows, the last one holding the remainder."""
        total = max(rows, 1)
        heights = [min(height, total - start) for start in range(0, total, height)]
        return cls(builders=tuple(PatternBuilder(rows=each, channels=channels) for each in heights), height=height)

    def address(self, row: int) -> tuple[PatternBuilder, int] | None:
        """The builder and offset a row falls on, or nothing when it lies past the end of the song."""
        index, offset = divmod(row, self.height)
        if index >= len(self.builders) or offset >= self.builders[index].rows:
            return None

        return self.builders[index], offset

    def place(self, row: int, channel: int, cell: Cell) -> bool:
        """Write a cell at an absolute row, reporting whether the row was inside the song."""
        located = self.address(row)
        if located is None:
            return False

        builder, offset = located
        builder.place(offset, channel, cell)
        return True

    def read(self, row: int, channel: int) -> Cell | None:
        """The cell already written at an absolute row, or nothing when the row lies past the end."""
        located = self.address(row)
        if located is None:
            return None

        builder, offset = located
        return builder.read(offset, channel)

    def free_effect_channel(self, row: int) -> int | None:
        """The lowest channel on an absolute row whose effect column is still free."""
        located = self.address(row)
        if located is None:
            return None

        builder, offset = located
        return builder.free_effect_channel(offset)

    def build(self) -> tuple[Pattern, ...]:
        """Freeze every grid written so far."""
        return tuple(builder.build() for builder in self.builders)


def _note_cell(voice: Voice, *, instrument: int) -> Cell:
    """The cell that starts a voice, carrying a note delay when it begins partway into its row."""
    effect = XM_EFFECTS.note_delay(voice.start.delay) if voice.start.delayed else None
    return Cell(
        note=tracker_note(voice.note.pitch),
        instrument=instrument,
        volume=tracker_volume(voice.note.velocity),
        effect=effect,
    )


def _place_notes(grids: Grids, allocation: Allocation, *, instrument: int) -> None:
    for voice in allocation.voices:
        grids.place(voice.start.row, voice.channel, _note_cell(voice, instrument=instrument))


def _place_releases(grids: Grids, allocation: Allocation) -> None:
    for voice in allocation.voices:
        if not voice.releases_later:
            continue

        occupant = grids.read(voice.release_row, voice.channel)
        if occupant is not None and occupant.note is None:
            grids.place(voice.release_row, voice.channel, Cell(note=NoteCommand.OFF))


def _place_tempos(grids: Grids, tempos: Sequence[TempoEvent], grid: RowGrid) -> list[TempoEvent]:
    """Write every tempo change past the opening one, returning those with nowhere to go."""
    dropped: list[TempoEvent] = []
    for tempo in tempos[1:]:
        row = grid.row_of(tempo.tick)
        channel = grids.free_effect_channel(row)
        if channel is None:
            dropped.append(tempo)
            continue

        effect = XM_EFFECTS.set_tempo(
            playable_tempo(tempo.beats_per_minute, speed=grid.speed, rows_per_beat=grid.rows_per_beat)
        )
        occupant = grids.read(row, channel)
        assert occupant is not None  # the row was addressable a moment ago
        grids.place(row, channel, occupant.model_copy(update={"effect": effect}))

    return dropped


@dataclass(frozen=True)
class Grid:
    """The finished patterns, and the tempo changes the grid had no effect column left to carry."""

    patterns: tuple[Pattern, ...]
    dropped_tempos: tuple[TempoEvent, ...]


def build_patterns(
    grids: Grids,
    allocation: Allocation,
    tempos: Sequence[TempoEvent],
    grid: RowGrid,
    *,
    instrument: int,
) -> Grid:
    """Lay the voices and tempo changes of one song onto grids already cut to its length."""
    _place_notes(grids, allocation, instrument=instrument)
    _place_releases(grids, allocation)
    dropped = _place_tempos(grids, tempos, grid)
    return Grid(patterns=grids.build(), dropped_tempos=tuple(dropped))
