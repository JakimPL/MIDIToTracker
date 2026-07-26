from __future__ import annotations

from midi2tracker.timing.grid import RowGrid
from midi2tracker.voices.allocation import allocate
from tests.conftest import midi_song, note


def test_notes_that_never_overlap_all_share_one_channel(grid: RowGrid) -> None:
    song = midi_song(note(0, 24), note(96, 24), note(192, 24))
    allocation = allocate(song, grid, channels=8)
    assert {voice.channel for voice in allocation.voices} == {0}
    assert allocation.channels == 1
    assert allocation.stolen == 0


def test_overlapping_notes_are_spread_over_the_channels_they_need(grid: RowGrid) -> None:
    song = midi_song(*(note(0, 192, pitch=60 + step) for step in range(4)))
    allocation = allocate(song, grid, channels=8)
    assert sorted(voice.channel for voice in allocation.voices) == [0, 1, 2, 3]
    assert allocation.channels == 4


def test_a_channel_is_free_again_the_row_its_voice_releases_on(grid: RowGrid) -> None:
    # A tracker cell that starts a note also ends whatever the channel was playing, so a note may begin
    # on the very row the previous one ends.
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    song = midi_song(note(0, ticks_per_row), note(ticks_per_row, ticks_per_row))
    allocation = allocate(song, grid, channels=8)
    assert [voice.channel for voice in allocation.voices] == [0, 0]


def test_a_note_with_no_channel_free_takes_the_oldest_one(grid: RowGrid) -> None:
    # The displaced voice is the one nearest its own end, and the loss is counted rather than passed over.
    song = midi_song(note(0, 480, pitch=60), note(48, 480, pitch=62), note(96, 480, pitch=64))
    allocation = allocate(song, grid, channels=2)
    assert allocation.stolen == 1
    assert allocation.voices[2].channel == allocation.voices[0].channel


def test_a_single_channel_carries_a_whole_chord_one_note_at_a_time(grid: RowGrid) -> None:
    song = midi_song(*(note(0, 192, pitch=60 + step) for step in range(4)))
    allocation = allocate(song, grid, channels=1)
    assert {voice.channel for voice in allocation.voices} == {0}
    assert allocation.stolen == 3


def test_a_piece_with_no_notes_still_reports_a_channel(grid: RowGrid) -> None:
    allocation = allocate(midi_song(), grid, channels=8)
    assert allocation.voices == ()
    assert allocation.channels == 1


def test_every_voice_keeps_the_note_it_was_placed_from(grid: RowGrid) -> None:
    song = midi_song(note(0, 24, pitch=60, velocity=90), note(48, 24, pitch=64, velocity=30))
    voices = allocate(song, grid, channels=4).voices
    assert [(voice.note.pitch, voice.note.velocity) for voice in voices] == [(60, 90), (64, 30)]
    assert [voice.start.row for voice in voices] == [grid.row_of(0), grid.row_of(48)]
    assert [voice.release_row for voice in voices] == [grid.row_of(24), grid.row_of(72)]
