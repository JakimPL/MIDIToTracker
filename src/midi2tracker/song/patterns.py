from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from trackmod.core.notes.command import NoteCommand
from trackmod.core.patterns.builder import PatternBuilder
from trackmod.core.patterns.cell import Cell
from trackmod.core.patterns.grid import Pattern

from midi2tracker.midi.events import TempoEvent
from midi2tracker.song.sounding import Sounded, Sounding
from midi2tracker.timing.grid import RowGrid
from midi2tracker.timing.tempo import playable_tempo
from midi2tracker.tracker.target import TrackerTarget


@dataclass(frozen=True)
class Grids:
    """The pattern builders of one song, addressed by absolute row.

    Holding them behind one address space is what lets the passes work in the song's own rows rather than
    each translating a pattern and an offset for itself.
    """

    builders: tuple[PatternBuilder, ...]
    height: int

    @classmethod
    def covering(cls, rows: int, *, channels: int, height: int, minimum: int) -> Grids:
        """Enough patterns of ``height`` rows to hold ``rows`` rows, each at least ``minimum`` tall.

        A format stating a floor for a pattern's height applies it to the trailing pattern as well, so a
        remainder shorter than the floor is padded up to it and the piece ends on silent rows.

        The height a caller asks for is at least the floor, which
        :func:`~midi2tracker.song.height.pattern_height` is what guarantees.
        """
        total = max(rows, 1)
        heights = [max(minimum, min(height, total - start)) for start in range(0, total, height)]
        return cls(
            builders=tuple(PatternBuilder(rows=each, channels=channels) for each in heights),
            height=height,
        )

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


def _note_cell(sounded: Sounded, *, target: TrackerTarget) -> Cell:
    """The cell that starts a voice, carrying a note delay when it begins partway into its row."""
    voice = sounded.voice
    effect = target.effects.note_delay(voice.start.delay) if voice.start.delayed else None
    return Cell(
        note=target.key(voice.note.pitch),
        instrument=sounded.voicing.slot,
        volume=sounded.voicing.volume,
        effect=effect,
    )


def _place_notes(grids: Grids, sounding: Sounding, *, target: TrackerTarget) -> None:
    for sounded in sounding.sounded:
        grids.place(
            sounded.voice.start.row,
            sounded.voice.channel,
            _note_cell(sounded, target=target),
        )


def _place_releases(grids: Grids, sounding: Sounding) -> None:
    """Write a key-off where each sounded voice ends, so only a note the module states is released."""
    for sounded in sounding.sounded:
        voice = sounded.voice
        if not voice.releases_later:
            continue

        occupant = grids.read(voice.release_row, voice.channel)
        if occupant is not None and occupant.note is None:
            grids.place(voice.release_row, voice.channel, Cell(note=NoteCommand.OFF))


def _place_tempos(
    grids: Grids,
    tempos: Sequence[TempoEvent],
    grid: RowGrid,
    *,
    target: TrackerTarget,
) -> list[TempoEvent]:
    """Write every tempo change past the opening one, returning those with nowhere to go."""
    dropped: list[TempoEvent] = []
    for tempo in tempos[1:]:
        row = grid.row_of(tempo.tick)
        channel = grids.free_effect_channel(row)
        if channel is None:
            dropped.append(tempo)
            continue

        effect = target.effects.set_tempo(
            playable_tempo(
                tempo.beats_per_minute,
                speed=grid.speed,
                rows_per_beat=grid.rows_per_beat,
                target=target,
            )
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
    sounding: Sounding,
    tempos: Sequence[TempoEvent],
    grid: RowGrid,
    *,
    target: TrackerTarget,
) -> Grid:
    """Lay the sounded voices and the tempo changes onto grids already cut to the song's length."""
    _place_notes(grids, sounding, target=target)
    _place_releases(grids, sounding)
    dropped = _place_tempos(grids, tempos, grid, target=target)
    return Grid(patterns=grids.build(), dropped_tempos=tuple(dropped))
