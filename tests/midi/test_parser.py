from __future__ import annotations

from pathlib import Path

import mido
import pytest

from midi2tracker.midi.parser import parse_midi
from midi2tracker.spec import DEFAULT_MICROSECONDS_PER_BEAT
from tests.conftest import PULSES, lift, pedal, press, write_midi


def sounded(path: Path) -> list[tuple[int, int, int]]:
    return [(note.pitch, note.tick_on, note.tick_off) for note in parse_midi(path).notes]


def test_notes_come_back_in_the_order_they_start(tmp_path: Path) -> None:
    path = write_midi(
        tmp_path / "in.mid",
        [press(67, 0), press(60, 0), lift(60, 48), lift(67, 96)],
    )
    assert sounded(path) == [(60, 0, 48), (67, 0, 96)]


def test_a_zero_velocity_note_on_ends_the_note(tmp_path: Path) -> None:
    # MIDI spells a release two ways, and a file using the second one must not leave notes hanging.
    path = write_midi(
        tmp_path / "in.mid",
        [press(60, 0), (mido.Message("note_on", note=60, velocity=0), 48), press(62, 96), lift(62, 144)],
    )
    assert sounded(path) == [(60, 0, 48), (62, 96, 144)]


def test_every_track_is_merged_into_one_stream(tmp_path: Path) -> None:
    # A tracker has channels, not tracks, so which track a note came from carries no meaning downstream.
    midi = mido.MidiFile(ticks_per_beat=PULSES)
    for pitch in (60, 64):
        track = mido.MidiTrack()
        track.append(mido.Message("note_on", note=pitch, velocity=100, time=0))
        track.append(mido.Message("note_off", note=pitch, velocity=0, time=48))
        midi.tracks.append(track)

    path = tmp_path / "in.mid"
    midi.save(str(path))
    assert sounded(path) == [(60, 0, 48), (64, 0, 48)]


def test_the_pedal_is_resolved_while_parsing(tmp_path: Path) -> None:
    path = write_midi(
        tmp_path / "in.mid",
        [press(60, 0), pedal(127, 10), lift(60, 24), pedal(0, 192)],
    )
    assert sounded(path) == [(60, 0, 192)]


def test_a_file_that_states_no_tempo_still_has_one(tmp_path: Path) -> None:
    path = write_midi(tmp_path / "in.mid", [press(60, 0), lift(60, 48)])
    tempos = parse_midi(path).tempos
    assert len(tempos) == 1
    assert tempos[0].microseconds_per_beat == DEFAULT_MICROSECONDS_PER_BEAT


def test_every_tempo_change_is_kept_in_order(tmp_path: Path) -> None:
    path = write_midi(
        tmp_path / "in.mid",
        [
            press(60, 0),
            (mido.MetaMessage("set_tempo", tempo=400_000), 96),
            (mido.MetaMessage("set_tempo", tempo=300_000), 192),
            lift(60, 288),
        ],
    )
    tempos = parse_midi(path).tempos
    assert [tempo.tick for tempo in tempos] == [0, 96, 192]
    assert [tempo.microseconds_per_beat for tempo in tempos] == [DEFAULT_MICROSECONDS_PER_BEAT, 400_000, 300_000]


def test_two_tempos_on_one_tick_leave_the_last_one_standing(tmp_path: Path) -> None:
    path = write_midi(
        tmp_path / "in.mid",
        [
            (mido.MetaMessage("set_tempo", tempo=400_000), 96),
            (mido.MetaMessage("set_tempo", tempo=300_000), 96),
            press(60, 0),
            lift(60, 192),
        ],
    )
    tempos = parse_midi(path).tempos
    assert [tempo.microseconds_per_beat for tempo in tempos] == [DEFAULT_MICROSECONDS_PER_BEAT, 300_000]


def test_a_note_left_hanging_rings_to_where_the_music_stops(tmp_path: Path) -> None:
    # The end-of-track marker may sit far past the last note; a hanging voice follows the music, not the
    # padding.
    path = write_midi(
        tmp_path / "in.mid",
        [press(60, 0), press(64, 96), lift(64, 192), (mido.MetaMessage("end_of_track"), 10_000)],
    )
    assert sounded(path) == [(60, 0, 192), (64, 96, 192)]


def test_an_empty_file_parses_into_a_song_with_a_tempo_and_no_notes(tmp_path: Path) -> None:
    path = write_midi(tmp_path / "in.mid", [(mido.MetaMessage("end_of_track"), 0)])
    song = parse_midi(path)
    assert song.notes == ()
    assert song.last_tick == 0
    assert song.fastest == pytest.approx(120.0)
