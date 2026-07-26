from __future__ import annotations

from pathlib import Path

import pytest
from trackmod.core.notes.command import NoteCommand
from trackmod.limits.compliance import Compliance
from trackmod.spec.grid import EMPTY
from trackmod.xm.module import XMModule
from trackmod.xm.spec.ranges import MAX_PATTERNS, MAX_ROWS

from midi2tracker.config import Config
from midi2tracker.convert import convert, row_grid
from midi2tracker.midi.parser import parse_midi
from midi2tracker.song.mapping import tracker_note
from midi2tracker.timing.speed import MAX_SPEED
from tests.conftest import lift, pedal, press, write_midi


def test_a_real_file_converts_into_a_writable_module(piece: Path) -> None:
    converted = convert(piece, Config())
    assert converted.writable
    assert converted.violations == ()
    assert converted.module.size().total == len(converted.module.to_bytes())


def test_the_module_reads_back_as_the_song_it_was_written_from(piece: Path) -> None:
    # Parsing with a decoder this converter did not write is the check that the bytes mean what the
    # model says: the notes, the channel count and the clock all have to survive the trip.
    converted = convert(piece, Config())
    recovered = XMModule.parse(converted.module.to_bytes()).song
    assert recovered.channels == converted.conversion.song.channels
    assert recovered.rows == converted.conversion.rows
    assert recovered.playback == converted.conversion.song.playback


def test_every_note_in_the_file_reaches_the_grid(piece: Path) -> None:
    # Each note fills one cell where it starts, and most fill a second where they release, so the note
    # column holds at least as many entries as the file has notes.
    converted = convert(piece, Config())
    placed = sum(int((pattern.note != EMPTY).sum()) for pattern in converted.conversion.song.patterns)
    assert placed >= len(converted.midi.notes)
    assert converted.conversion.stolen_notes == 0


def test_the_file_is_written_where_it_was_asked_for(piece: Path, tmp_path: Path) -> None:
    output = tmp_path / "out.xm"
    convert(piece, Config()).save(output)
    assert XMModule.load(output).song.channels > 0


def test_a_tempo_override_replaces_the_opening_tempo_only(piece: Path) -> None:
    original = parse_midi(piece)
    converted = convert(piece, Config(tempo=90.0))
    assert converted.midi.tempos[0].beats_per_minute == pytest.approx(90.0, abs=0.1)
    assert [tempo.tick for tempo in converted.midi.tempos] == [tempo.tick for tempo in original.tempos]
    assert converted.midi.tempos[1:] == original.tempos[1:]


def test_an_explicit_speed_is_used_instead_of_the_chosen_one(piece: Path) -> None:
    converted = convert(piece, Config(speed=4))
    assert converted.grid.speed == 4
    assert converted.conversion.song.playback.speed == 4


def test_the_chosen_speed_never_leaves_the_addressable_range(piece: Path) -> None:
    for rows_per_beat in (1, 2, 4, 8, 15, 32):
        grid = row_grid(parse_midi(piece), Config(rows_per_beat=rows_per_beat))
        assert 1 <= grid.speed <= MAX_SPEED


def test_the_instrument_slot_reserves_the_slots_below_it(piece: Path) -> None:
    converted = convert(piece, Config(instrument=5))
    instruments = converted.conversion.song.instruments
    assert len(instruments) == 5
    assert all(assignment is None for instrument in instruments[:4] for assignment in instrument.keymap)
    assert converted.writable


def test_a_channel_ceiling_costs_notes_rather_than_the_conversion(piece: Path) -> None:
    converted = convert(piece, Config(channels=1))
    assert converted.conversion.song.channels <= 2  # rounded up to a stereo pair
    assert converted.writable


def test_a_long_piece_at_a_short_pattern_height_still_fits_the_order_table(tmp_path: Path) -> None:
    # A height the piece cannot be cut at gives way, where the pre-migration writer crashed building an
    # order table longer than the format names.
    messages = []
    for index in range(1200):
        messages.extend([press(60, index * 96), lift(60, index * 96 + 48)])

    path = write_midi(tmp_path / "long.mid", messages)
    converted = convert(path, Config(pattern_rows=8, rows_per_beat=4))
    patterns = converted.conversion.song.patterns
    assert len(patterns) <= MAX_PATTERNS
    assert max(pattern.rows for pattern in patterns) <= MAX_ROWS
    assert converted.writable


def test_the_sustain_pedal_reaches_the_grid_as_a_longer_note(tmp_path: Path) -> None:
    path = write_midi(
        tmp_path / "pedal.mid",
        [press(60, 0), pedal(127, 8), lift(60, 24), pedal(0, 384)],
    )
    converted = convert(path, Config(rows_per_beat=4))
    grid = converted.grid
    patterns = converted.conversion.song.patterns
    assert patterns[0].cell(0, 0).note == tracker_note(60)
    assert patterns[0].cell(grid.row_of(384), 0).note == NoteCommand.OFF


def test_an_empty_file_converts_into_a_module_that_plays_nothing(tmp_path: Path) -> None:
    path = write_midi(tmp_path / "empty.mid", [press(60, 0), lift(60, 0)])
    converted = convert(path, Config())
    assert converted.writable
    assert converted.conversion.song.rows >= 1


def test_the_module_is_canonical_by_default(piece: Path) -> None:
    # Canonical is what makes the file open in FastTracker 2 itself, not only in a modern player.
    assert convert(piece, Config()).module.compliance is Compliance.CANONICAL
