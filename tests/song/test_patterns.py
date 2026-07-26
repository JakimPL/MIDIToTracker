from __future__ import annotations

from trackmod.core.notes.command import NoteCommand
from trackmod.core.patterns.cell import Cell
from trackmod.xm.effects.catalog import XM_EFFECTS
from trackmod.xm.effects.command import XMEffect

from midi2tracker.midi.events import MidiSong, TempoEvent
from midi2tracker.song.mapping import tracker_note, tracker_volume
from midi2tracker.song.patterns import Grid, Grids, build_patterns
from midi2tracker.timing.grid import RowGrid
from midi2tracker.voices.allocation import allocate
from tests.conftest import midi_song, note

DEFAULT_TEMPO = TempoEvent(tick=0, microseconds_per_beat=500_000)


def written(song: MidiSong, grid: RowGrid, *, channels: int = 4, height: int = 64, instrument: int = 0) -> Grid:
    """One song laid onto grids of a fixed height, which is what each pass is checked through."""
    allocation = allocate(song, grid, channels=channels)
    rows = grid.row_of(song.last_tick) + grid.rows_per_beat + 1
    grids = Grids.covering(rows, channels=channels, height=height)
    return build_patterns(grids, allocation, song.tempos, grid, instrument=instrument)


def cell_at(patterns, row: int, channel: int, *, height: int = 64) -> Cell:
    return patterns[row // height].cell(row % height, channel)


# -- the address space ------------------------------------------------------


def test_the_grids_cover_the_rows_asked_for_and_no_more() -> None:
    grids = Grids.covering(150, channels=2, height=64)
    assert [builder.rows for builder in grids.builders] == [64, 64, 22]


def test_a_row_past_the_end_is_reported_rather_than_written() -> None:
    grids = Grids.covering(10, channels=2, height=64)
    assert grids.place(200, 0, Cell(note=NoteCommand.OFF)) is False
    assert grids.read(200, 0) is None
    assert grids.free_effect_channel(200) is None


def test_an_empty_song_still_gets_a_pattern_to_live_in() -> None:
    assert len(Grids.covering(0, channels=2, height=64).builders) == 1


# -- the note pass ----------------------------------------------------------


def test_a_note_fills_its_cells_note_instrument_and_volume(grid: RowGrid) -> None:
    song = midi_song(note(0, 48, pitch=64, velocity=100))
    result = written(song, grid, instrument=3)
    cell = cell_at(result.patterns, 0, 0)
    assert cell.note == tracker_note(64)
    assert cell.instrument == 3
    assert cell.volume == tracker_volume(100)


def test_a_note_starting_on_its_row_needs_no_effect(grid: RowGrid) -> None:
    song = midi_song(note(0, 48))
    result = written(song, grid)
    assert cell_at(result.patterns, 0, 0).effect is None


def test_a_note_starting_partway_into_its_row_carries_a_note_delay(grid: RowGrid) -> None:
    # The row is the coarse position and the delay the remainder, which is the only sub-row resolution
    # a tracker offers.
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    song = midi_song(note(ticks_per_row // 2, 48))
    result = written(song, grid)
    effect = cell_at(result.patterns, 0, 0).effect
    assert effect == XM_EFFECTS.note_delay(grid.speed // 2)


# -- the release pass -------------------------------------------------------


def test_a_note_that_releases_later_gets_a_key_off_on_that_row(grid: RowGrid) -> None:
    song = midi_song(note(0, 96))
    result = written(song, grid)
    assert cell_at(result.patterns, grid.row_of(96), 0).note == NoteCommand.OFF


def test_a_note_that_starts_and_ends_in_one_row_needs_no_key_off(grid: RowGrid) -> None:
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    song = midi_song(note(0, ticks_per_row // 3))
    result = written(song, grid)
    assert cell_at(result.patterns, 0, 0).note == tracker_note(60)
    assert cell_at(result.patterns, 1, 0).note is None


def test_a_note_starting_where_another_releases_keeps_the_row(grid: RowGrid) -> None:
    # One cell says one thing, and starting the new voice is what the listener hears; the old one ends
    # when the channel is taken anyway.
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    song = midi_song(note(0, ticks_per_row), note(ticks_per_row, ticks_per_row))
    result = written(song, grid)
    assert cell_at(result.patterns, 1, 0).note == tracker_note(60)
    assert cell_at(result.patterns, 1, 0).volume is not None


# -- the tempo pass ---------------------------------------------------------


def test_a_tempo_change_lands_on_the_lowest_free_effect_column(grid: RowGrid) -> None:
    change = TempoEvent(tick=96, microseconds_per_beat=400_000)
    song = midi_song(note(0, 384), tempos=(DEFAULT_TEMPO, change))
    result = written(song, grid)
    cell = cell_at(result.patterns, grid.row_of(96), 0)
    assert cell.effect is not None
    assert cell.effect.command == XMEffect.SET_SPEED
    assert result.dropped_tempos == ()


def test_a_tempo_change_leaves_the_note_in_the_cell_it_shares(grid: RowGrid) -> None:
    # A global effect belongs to the row, so it rides alongside whatever voice already holds that cell.
    change = TempoEvent(tick=96, microseconds_per_beat=400_000)
    song = midi_song(note(96, 96), tempos=(DEFAULT_TEMPO, change))
    result = written(song, grid)
    cell = cell_at(result.patterns, grid.row_of(96), 0)
    assert cell.note == tracker_note(60)
    assert cell.effect is not None


def test_the_opening_tempo_is_left_to_the_header(grid: RowGrid) -> None:
    song = midi_song(note(0, 96))
    result = written(song, grid)
    assert all(cell_at(result.patterns, 0, channel).effect is None for channel in range(4))


def test_a_tempo_change_with_no_free_column_is_reported(grid: RowGrid) -> None:
    # Every channel already carrying an effect is a real loss, so it travels back to the caller instead
    # of the change being dropped in silence.
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    delayed = ticks_per_row // 2
    song = midi_song(
        *(note(delayed, 96, pitch=60 + step) for step in range(2)),
        tempos=(DEFAULT_TEMPO, TempoEvent(tick=delayed, microseconds_per_beat=400_000)),
    )
    result = written(song, grid, channels=2)
    assert len(result.dropped_tempos) == 1
