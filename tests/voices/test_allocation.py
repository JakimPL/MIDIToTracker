from __future__ import annotations

import pytest

from midi2tracker.arrangement.mode import ChannelAllocation
from midi2tracker.arrangement.track import Track
from midi2tracker.midi.events import NoteEvent
from midi2tracker.timing.grid import RowGrid
from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.voices.allocation import Allocation, allocate
from midi2tracker.voices.error import AllocationError
from tests.conftest import canonical, midi_song, note, track

IMPULSE = canonical(TrackerFormat.IT)
FAST = canonical(TrackerFormat.XM)

PACKED = ChannelAllocation.PACKED
SEPARATED = ChannelAllocation.SEPARATED


def placed(grid: RowGrid, *tracks: Track, allocation: ChannelAllocation = SEPARATED) -> Allocation:
    """The channels a piece's tracks reach, held to what Impulse Tracker plays."""
    return allocate(tracks, grid, allocation=allocation, target=IMPULSE)


def chord(tick: int, voices: int, *, ticks: int = 192) -> tuple[NoteEvent, ...]:
    """Notes sounding together from ``tick``, which is what asks a track for channels of its own."""
    return tuple(note(tick, ticks, pitch=60 + step) for step in range(voices))


# -- one track --------------------------------------------------------------


def test_notes_that_never_overlap_all_share_one_channel(grid: RowGrid) -> None:
    song = midi_song(note(0, 24), note(96, 24), note(192, 24))
    allocation = placed(grid, track(song, channels=8))
    assert {voice.channel for voice in allocation.voices} == {0}
    assert allocation.tracks[0].channels == 1
    assert allocation.stolen == 0


def test_overlapping_notes_are_spread_over_the_channels_they_need(grid: RowGrid) -> None:
    allocation = placed(grid, track(midi_song(*chord(0, 4)), channels=8))
    assert sorted(voice.channel for voice in allocation.voices) == [0, 1, 2, 3]
    assert allocation.tracks[0].channels == 4
    assert allocation.width == 4


def test_a_channel_is_free_again_the_row_its_voice_releases_on(grid: RowGrid) -> None:
    # A tracker cell that starts a note also ends whatever the channel was playing, so a note may begin
    # on the very row the previous one ends.
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    song = midi_song(note(0, ticks_per_row), note(ticks_per_row, ticks_per_row))
    assert [voice.channel for voice in placed(grid, track(song, channels=8)).voices] == [0, 0]


def test_a_note_released_inside_its_own_row_keeps_the_cell_it_was_written_into(grid: RowGrid) -> None:
    # One cell states one note, so a voice that starts and ends inside a row still holds that row and the
    # next note begins on a channel of its own rather than replacing it.
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    short = ticks_per_row // 3
    song = midi_song(note(0, short, pitch=60), note(short, short, pitch=64))
    assert [voice.channel for voice in placed(grid, track(song, channels=8)).voices] == [0, 1]


def test_a_note_with_no_channel_free_takes_the_oldest_one(grid: RowGrid) -> None:
    # The displaced voice is the one nearest its own end, and the loss is counted rather than passed over.
    song = midi_song(note(0, 480, pitch=60), note(48, 480, pitch=62), note(96, 480, pitch=64))
    allocation = placed(grid, track(song, channels=2))
    assert allocation.stolen == 1
    assert allocation.voices[2].channel == allocation.voices[0].channel


def test_a_single_channel_carries_a_whole_chord_one_note_at_a_time(grid: RowGrid) -> None:
    allocation = placed(grid, track(midi_song(*chord(0, 4)), channels=1))
    assert {voice.channel for voice in allocation.voices} == {0}
    assert allocation.stolen == 3


def test_a_piece_with_no_notes_still_declares_a_pair_of_channels(grid: RowGrid) -> None:
    allocation = placed(grid, track(midi_song(), channels=8))
    assert allocation.voices == ()
    assert allocation.tracks[0].channels == 0
    assert allocation.width == 2


def test_a_width_reaching_an_odd_channel_declares_the_pair_it_sits_in(grid: RowGrid) -> None:
    assert placed(grid, track(midi_song(*chord(0, 3)), channels=8)).width == 4


def test_every_voice_keeps_the_note_it_was_placed_from(grid: RowGrid) -> None:
    song = midi_song(note(0, 24, pitch=60, velocity=90), note(48, 24, pitch=64, velocity=30))
    voices = placed(grid, track(song, channels=4)).voices
    assert [(voice.note.pitch, voice.note.velocity) for voice in voices] == [(60, 90), (64, 30)]
    assert [voice.start.row for voice in voices] == [grid.row_of(0), grid.row_of(48)]
    assert [voice.release_row for voice in voices] == [grid.row_of(24), grid.row_of(72)]


def test_one_track_is_laid_out_the_same_whichever_way_the_tracks_share(grid: RowGrid) -> None:
    """A piece read from one file has nothing to share with, so both ways state the same channels."""
    song = midi_song(*chord(0, 3), note(384, 24))
    single = track(song, channels=8)
    assert placed(grid, single, allocation=PACKED).voices == placed(grid, single, allocation=SEPARATED).voices


# -- tracks kept apart ------------------------------------------------------


def test_each_track_takes_a_run_of_channels_of_its_own(grid: RowGrid) -> None:
    allocation = placed(
        grid,
        track(midi_song(*chord(0, 2)), channels=8, name="bass"),
        track(midi_song(*chord(0, 3)), channels=8, name="brass"),
        allocation=SEPARATED,
    )
    bass = {voice.channel for voice in allocation.voices if voice.track == 0}
    brass = {voice.channel for voice in allocation.voices if voice.track == 1}
    assert bass == {0, 1} and brass == {2, 3, 4}
    assert [entry.channels for entry in allocation.tracks] == [2, 3]
    assert allocation.width == 6


def test_a_track_playing_nothing_takes_no_channels_from_the_ones_after_it(grid: RowGrid) -> None:
    allocation = placed(
        grid,
        track(midi_song(*chord(0, 2)), channels=8, name="bass"),
        track(midi_song(), channels=8, name="silent"),
        track(midi_song(note(0, 24)), channels=8, name="brass"),
        allocation=SEPARATED,
    )
    assert [entry.channels for entry in allocation.tracks] == [2, 0, 1]
    assert [voice.channel for voice in allocation.voices if voice.track == 2] == [2]


def test_a_track_is_held_to_its_own_ceiling_rather_than_the_piece_s(grid: RowGrid) -> None:
    allocation = placed(
        grid,
        track(midi_song(*chord(0, 4)), channels=1, name="bass"),
        track(midi_song(*chord(0, 2)), channels=8, name="brass"),
        allocation=SEPARATED,
    )
    assert [entry.stolen for entry in allocation.tracks] == [3, 0]
    assert allocation.stolen == 3
    assert [entry.channels for entry in allocation.tracks] == [1, 2]


def test_a_voice_names_the_track_whose_file_it_was_read_from(grid: RowGrid) -> None:
    allocation = placed(
        grid,
        track(midi_song(note(0, 24, pitch=48)), channels=8, name="bass"),
        track(midi_song(note(0, 24, pitch=72)), channels=8, name="brass"),
    )
    assert {(voice.track, voice.note.pitch) for voice in allocation.voices} == {(0, 48), (1, 72)}
    assert [entry.name for entry in allocation.tracks] == ["bass", "brass"]


# -- tracks sharing one pool ------------------------------------------------


def test_a_channel_one_track_frees_carries_the_next_note_of_another(grid: RowGrid) -> None:
    tracks = (track(midi_song(note(0, 24)), channels=8), track(midi_song(note(48, 24)), channels=8))
    assert {voice.channel for voice in placed(grid, *tracks, allocation=PACKED).voices} == {0}
    assert {voice.channel for voice in placed(grid, *tracks, allocation=SEPARATED).voices} == {0, 1}


def test_tracks_that_never_sound_together_span_the_channels_one_of_them_needs(grid: RowGrid) -> None:
    tracks = (
        track(midi_song(*chord(0, 2)), channels=8, name="bass"),
        track(midi_song(*chord(384, 2)), channels=8, name="brass"),
    )
    assert placed(grid, *tracks, allocation=PACKED).width == 2
    assert placed(grid, *tracks, allocation=SEPARATED).width == 4


def test_a_track_at_its_ceiling_gives_up_its_own_voice_rather_than_taking_another_track_s(
    grid: RowGrid,
) -> None:
    # A ceiling means the same thing in both modes, so a narrow track stays narrow beside a wide one.
    allocation = placed(
        grid,
        track(midi_song(note(0, 192, pitch=60), note(24, 192, pitch=62)), channels=1, name="bass"),
        track(midi_song(note(0, 192, pitch=48)), channels=8, name="brass"),
        allocation=PACKED,
    )
    bass = [voice.channel for voice in allocation.voices if voice.track == 0]
    brass = [voice.channel for voice in allocation.voices if voice.track == 1]
    assert bass == [0, 0] and brass == [1]
    assert [entry.stolen for entry in allocation.tracks] == [1, 0]


# -- what the format carries ------------------------------------------------


def test_a_piece_spreading_past_the_format_is_refused_before_anything_is_written(grid: RowGrid) -> None:
    tracks = tuple(
        track(midi_song(*chord(index * 960, 12)), channels=16, name=name)
        for index, name in enumerate(("bass", "brass", "woodwinds"))
    )
    with pytest.raises(AllocationError) as refused:
        allocate(tracks, grid, allocation=SEPARATED, target=FAST)

    stated = str(refused.value)
    assert "separated allocation reaches 36 channels" in stated
    assert "XM plays 32" in stated
    assert "bass 12, brass 12, woodwinds 12" in stated
    assert "packed allocation reaches 12" in stated


def test_a_piece_no_way_of_sharing_makes_fit_names_the_wider_one_too(grid: RowGrid) -> None:
    tracks = tuple(track(midi_song(*chord(0, 12)), channels=16, name=name) for name in ("bass", "brass", "woodwinds"))
    with pytest.raises(AllocationError, match="separated allocation reaches 36"):
        allocate(tracks, grid, allocation=PACKED, target=FAST)


def test_a_piece_the_format_carries_is_laid_out_rather_than_refused(grid: RowGrid) -> None:
    tracks = tuple(track(midi_song(*chord(0, 12)), channels=16) for _ in range(3))
    assert allocate(tracks, grid, allocation=PACKED, target=IMPULSE).width == 36
