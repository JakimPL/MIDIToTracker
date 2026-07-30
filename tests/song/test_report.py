from __future__ import annotations

from pathlib import Path

from midi2tracker.arrangement.build import arrange
from midi2tracker.config import Config
from midi2tracker.convert import row_grid
from midi2tracker.settings import ChannelAllocation
from midi2tracker.song.report import TrackReport, report
from midi2tracker.song.sounding import sound
from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.voices.allocation import allocate
from tests.conftest import SAMPLED_KEYS, instrument_file, lift, press, write_midi


def reported(path: Path, config: Config) -> tuple[TrackReport, ...]:
    """What each track of the piece at ``path`` cost, read the way a conversion reads it."""
    arrangement = arrange(path, config)
    grid = row_grid(arrangement.timing, config)
    allocation = allocate(arrangement.tracks, grid, allocation=arrangement.allocation, target=config.target)
    sounding = sound(allocation, ensemble=arrangement.ensemble, target=config.target)
    return report(arrangement, allocation, sounding)


def document(path: Path, stated: str) -> Path:
    path.write_text(stated, encoding="utf-8")
    return path


def test_each_track_states_the_notes_it_plays_and_the_channels_it_reached(tmp_path: Path) -> None:
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96), press(50, 96), lift(50, 192)])
    write_midi(
        tmp_path / "lead.mid",
        [message for pitch in (72, 74, 76) for message in (press(pitch, 0), lift(pitch, 192))],
    )
    path = document(tmp_path / "song.yaml", "tracks:\n  bass.mid:\n  lead.mid:\n")

    tracks = reported(path, Config())
    assert [track.name for track in tracks] == ["bass", "lead"]
    assert [track.notes for track in tracks] == [2, 3]
    assert [track.channels for track in tracks] == [1, 3]
    assert all(track.left_out == 0 for track in tracks)


def test_the_track_that_ran_out_of_channels_is_the_one_the_count_sits_under(tmp_path: Path) -> None:
    # A ceiling is raised on one track at a time, so the displaced voices name the track to raise it on.
    chord = [message for pitch in (60, 62, 64) for message in (press(pitch, 0), lift(pitch, 192))]
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 192)])
    write_midi(tmp_path / "lead.mid", chord)
    path = document(tmp_path / "song.yaml", "tracks:\n  bass.mid:\n  lead.mid:\n    channels: 1\n")

    tracks = reported(path, Config())
    assert [track.stolen for track in tracks] == [0, 2]


def test_the_notes_a_bank_leaves_unsampled_sit_under_the_track_that_plays_through_it(tmp_path: Path) -> None:
    outside = min(SAMPLED_KEYS) - 1
    instrument_file(tmp_path / "piano.it")
    write_midi(tmp_path / "bass.mid", [press(outside, 0), lift(outside, 96)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96)])
    path = document(
        tmp_path / "song.yaml",
        "tracks:\n  bass.mid:\n    instrument_file: piano.it\n  lead.mid:\n    instrument_file: piano.it\n",
    )

    tracks = reported(path, Config())
    assert [[note.pitch for note in track.silent] for track in tracks] == [[outside], []]
    assert [track.left_out for track in tracks] == [1, 0]


def test_the_notes_past_the_keys_the_format_numbers_name_the_track_that_plays_them(tmp_path: Path) -> None:
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96)])
    write_midi(tmp_path / "lead.mid", [press(120, 0), lift(120, 96)])
    path = document(tmp_path / "song.yaml", "tracks:\n  bass.mid:\n  lead.mid:\n")

    tracks = reported(path, Config(format=TrackerFormat.XM))
    assert [[note.pitch for note in track.unplayable] for track in tracks] == [[], [120]]


def test_a_track_reaches_the_same_channels_however_the_tracks_share_the_table(tmp_path: Path) -> None:
    # What a ceiling means is the track's own polyphony, so packing changes where a track sits rather
    # than how wide it is.
    write_midi(
        tmp_path / "bass.mid",
        [message for pitch in (48, 50) for message in (press(pitch, 0), lift(pitch, 96))],
    )
    write_midi(tmp_path / "lead.mid", [press(72, 192), lift(72, 288)])
    path = document(tmp_path / "song.yaml", "tracks:\n  bass.mid:\n  lead.mid:\n")

    separated = reported(path, Config(allocation=ChannelAllocation.SEPARATED))
    packed = reported(path, Config(allocation=ChannelAllocation.PACKED))
    assert [track.channels for track in separated] == [2, 1]
    assert [track.channels for track in packed] == [2, 1]
