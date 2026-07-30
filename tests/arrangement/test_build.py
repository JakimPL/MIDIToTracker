from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from midi2tracker.arrangement.build import arrange
from midi2tracker.arrangement.error import ArrangementError
from midi2tracker.config import Config
from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.velocity import VELOCITY_COUNT
from midi2tracker.settings import ChannelAllocation
from tests.conftest import (
    bank_container,
    instrument_file,
    lift,
    press,
    standalone_instrument,
    tempo,
    velocity_map_file,
    velocity_table,
    write_midi,
)

FIRST_TRACK = 0
SECOND_TRACK = 1


def document(path: Path, stated: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(stated), encoding="utf-8")
    return path


def bassline(path: Path, *, pulses: int) -> Path:
    return write_midi(path, [press(48, 0), lift(48, pulses), press(50, pulses), lift(50, pulses * 2)], pulses=pulses)


def melody(path: Path, *, pulses: int) -> Path:
    return write_midi(path, [press(72, 0), lift(72, pulses * 4)], pulses=pulses)


def test_two_files_of_different_resolutions_meet_on_one_scale(tmp_path: Path) -> None:
    """480 and 384 pulses a beat combine on 1920, and every note keeps the beat its own file put it on.

    This is what lets a piece be assembled from stems a producer wrote at whatever resolution each was
    written at, with no note nudged off its beat.
    """
    bassline(tmp_path / "bass.mid", pulses=480)
    melody(tmp_path / "lead.mid", pulses=384)
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": None, "lead.mid": None}})

    arrangement = arrange(path, Config())
    assert arrangement.pulses_per_beat == 1920
    assert [track.midi.pulses_per_beat for track in arrangement.tracks] == [1920, 1920]
    assert [note.tick_on for note in arrangement.tracks[FIRST_TRACK].midi.notes] == [0, 1920]
    assert [note.tick_on for note in arrangement.tracks[SECOND_TRACK].midi.notes] == [0]


def test_the_piece_ends_where_the_last_track_still_playing_does(tmp_path: Path) -> None:
    bassline(tmp_path / "bass.mid", pulses=480)
    melody(tmp_path / "lead.mid", pulses=384)
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": None, "lead.mid": None}})

    arrangement = arrange(path, Config())
    assert arrangement.last_tick == max(track.midi.last_tick for track in arrangement.tracks)
    assert arrangement.notes == 3


def test_the_named_clock_is_the_tempo_map_the_piece_follows(tmp_path: Path) -> None:
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96), tempo(100.0, 0)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96), tempo(150.0, 0)])
    path = document(tmp_path / "song.yaml", {"clock": "lead.mid", "tracks": {"bass.mid": None, "lead.mid": None}})

    arrangement = arrange(path, Config())
    assert arrangement.timekeeper == SECOND_TRACK
    assert round(arrangement.tempos[0].beats_per_minute) == 150


def test_the_first_track_keeps_the_time_when_no_clock_is_named(tmp_path: Path) -> None:
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96), tempo(100.0, 0)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96), tempo(150.0, 0)])
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": None, "lead.mid": None}})

    arrangement = arrange(path, Config())
    assert round(arrangement.tempos[0].beats_per_minute) == 100


def test_the_row_clock_keeps_up_with_the_fastest_the_timekeeper_reaches(tmp_path: Path) -> None:
    # A row has to be short enough for the quickest stretch of the map the module actually plays.
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96), tempo(100.0, 0), tempo(160.0, 48)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96), tempo(200.0, 0)])
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": None, "lead.mid": None}})
    assert round(arrange(path, Config()).fastest) == 160


def test_a_tempo_the_piece_does_not_follow_is_named_rather_than_dropped(tmp_path: Path) -> None:
    # A module keeps one clock, so a caller is told which track's timing went unread and can point at it.
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96), tempo(100.0, 0)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96), tempo(150.0, 0), tempo(90.0, 48)])
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": None, "lead.mid": None}})

    unheard = arrange(path, Config()).unheard_tempos
    assert [entry.track for entry in unheard] == ["lead", "lead"]
    assert sorted(round(entry.tempo.beats_per_minute) for entry in unheard) == [90, 150]


def test_tracks_agreeing_with_the_clock_leave_nothing_unheard(tmp_path: Path) -> None:
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96), tempo(120.0, 0)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96), tempo(120.0, 0)])
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": None, "lead.mid": None}})
    assert arrange(path, Config()).unheard_tempos == ()


def test_the_stated_tempo_replaces_the_opening_of_the_track_that_keeps_time(tmp_path: Path) -> None:
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96), tempo(100.0, 0)])
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": None}})
    assert round(arrange(path, Config(tempo=180.0)).tempos[0].beats_per_minute) == 180


def test_each_track_plays_through_the_bank_it_names(tmp_path: Path) -> None:
    bassline(tmp_path / "bass.mid", pulses=96)
    melody(tmp_path / "lead.mid", pulses=96)
    instrument_file(tmp_path / "low.it", name="Low")
    instrument_file(tmp_path / "high.it", name="High")
    path = document(
        tmp_path / "song.yaml",
        {
            "tracks": {
                "bass.mid": {"instrument_file": "low.it"},
                "lead.mid": {"instrument_file": "high.it"},
            }
        },
    )

    arrangement = arrange(path, Config())
    assert [track.bank.name for track in arrangement.tracks] == ["Low 0", "High 0"]
    assert [placement.offset for placement in arrangement.ensemble.placements] == [0, 1]


def test_two_tracks_naming_one_bank_are_placed_on_the_same_slots(tmp_path: Path) -> None:
    """A piece assembled from stems of one instrument costs that instrument once.

    The tracks are separate music and the same voice, so what they share is the slots and the samples
    behind them.
    """
    bassline(tmp_path / "left.mid", pulses=96)
    melody(tmp_path / "right.mid", pulses=96)
    instrument_file(tmp_path / "piano.it", name="Piano")
    path = document(
        tmp_path / "song.yaml",
        {
            "tracks": {
                "left.mid": {"instrument_file": "piano.it"},
                "right.mid": {"instrument_file": "piano.it"},
            }
        },
    )

    arrangement = arrange(path, Config())
    instruments, samples = arrangement.ensemble.content
    assert len(arrangement.ensemble.placements) == 1
    assert arrangement.ensemble.tracks == (0, 0)
    assert len(instruments) == 1 and len(samples) == 1


def test_a_track_states_the_layers_its_bank_is_made_of(tmp_path: Path) -> None:
    bassline(tmp_path / "wood.mid", pulses=96)
    standalone_instrument(tmp_path / "soft.iti", name="Soft")
    standalone_instrument(tmp_path / "loud.iti", name="Loud")
    path = document(
        tmp_path / "song.yaml",
        {
            "tracks": {
                "wood.mid": {
                    "name": "Woodwinds",
                    "layers": [
                        {
                            "source": {"file": "soft.iti"},
                            "select": {"velocity": {"low": 0, "high": 63}},
                            "velocity_map": velocity_table([9] * VELOCITY_COUNT),
                        },
                        {"source": {"file": "loud.iti"}},
                    ],
                }
            }
        },
    )

    bank = arrange(path, Config()).tracks[FIRST_TRACK].bank
    assert bank.name == "Woodwinds"
    assert [unit.instrument.name for unit in bank.units] == ["Soft", "Loud"]


def test_a_track_naming_a_container_reads_the_bank_inside_it(tmp_path: Path) -> None:
    bassline(tmp_path / "bass.mid", pulses=96)
    source = instrument_file(tmp_path / "piano.it", name="Piano")
    bank_container(tmp_path / "Piano.bank", [{"source": {"file": "piano.it"}}], {"piano.it": source}, name="Piano")
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": "Piano.bank"}})
    assert arrange(path, Config()).tracks[FIRST_TRACK].bank.name == "Piano"


def test_a_track_naming_nothing_plays_the_reserved_slot(tmp_path: Path) -> None:
    bassline(tmp_path / "bass.mid", pulses=96)
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": None}})
    instruments, _ = arrange(path, Config()).ensemble.content
    assert len(instruments) == 1


def test_every_path_is_read_against_the_document(tmp_path: Path) -> None:
    # An arrangement moves as one directory, so nothing in it is read against the working directory.
    inner = tmp_path / "song"
    (inner / "stems").mkdir(parents=True)
    bassline(inner / "stems" / "bass.mid", pulses=96)
    instrument_file(inner / "piano.it", name="Piano")
    path = document(
        inner / "song.yaml",
        {"tracks": {"stems/bass.mid": {"instrument_file": "piano.it"}}},
    )
    assert arrange(path, Config()).tracks[FIRST_TRACK].bank.name == "Piano 0"


def test_a_track_holds_its_own_channel_ceiling(tmp_path: Path) -> None:
    bassline(tmp_path / "bass.mid", pulses=96)
    melody(tmp_path / "lead.mid", pulses=96)
    path = document(
        tmp_path / "song.yaml",
        {"tracks": {"bass.mid": {"channels": 2}, "lead.mid": None}},
    )
    arrangement = arrange(path, Config(channels=12))
    assert [track.channels for track in arrangement.tracks] == [2, 12]


def test_the_allocation_the_document_states_is_the_one_the_piece_takes(tmp_path: Path) -> None:
    bassline(tmp_path / "bass.mid", pulses=96)
    packed = document(tmp_path / "packed.yaml", {"allocation": "packed", "tracks": {"bass.mid": None}})
    plain = document(tmp_path / "plain.yaml", {"tracks": {"bass.mid": None}})
    assert arrange(packed, Config()).allocation is ChannelAllocation.PACKED
    assert arrange(plain, Config()).allocation is ChannelAllocation.SEPARATED


def test_one_midi_file_arranges_as_a_track_of_its_own(tmp_path: Path) -> None:
    """The single file and the document reach one object, so nothing downstream reads two shapes."""
    source = bassline(tmp_path / "bass.mid", pulses=96)
    instrument_file(tmp_path / "piano.it", name="Piano")
    arrangement = arrange(source, Config(instrument_file=tmp_path / "piano.it", channels=8))
    assert arrangement.name == "bass"
    assert len(arrangement.tracks) == 1
    assert arrangement.tracks[FIRST_TRACK].channels == 8
    assert arrangement.tracks[FIRST_TRACK].bank.name == "Piano 0"


def test_one_midi_file_reads_the_velocity_map_the_settings_name(tmp_path: Path) -> None:
    source = bassline(tmp_path / "bass.mid", pulses=96)
    instrument_file(tmp_path / "piano.it", name="Piano")
    stated = velocity_map_file(tmp_path / "measured.json", [23] * VELOCITY_COUNT)
    arrangement = arrange(source, Config(instrument_file=tmp_path / "piano.it", velocity_map=stated))
    layer = arrangement.tracks[FIRST_TRACK].bank.layers[0]
    assert layer.velocity.volume(100) == 23


def test_the_instruments_start_on_the_slot_the_settings_name(tmp_path: Path) -> None:
    source = bassline(tmp_path / "bass.mid", pulses=96)
    instrument_file(tmp_path / "piano.it", name="Piano")
    arrangement = arrange(source, Config(instrument_file=tmp_path / "piano.it", instrument=5))
    instruments, _ = arrangement.ensemble.content
    assert len(instruments) == 5
    assert arrangement.ensemble.placements[0].offset == 4


def test_a_midi_file_the_document_names_and_cannot_be_read_is_reported(tmp_path: Path) -> None:
    path = document(tmp_path / "song.yaml", {"tracks": {"absent.mid": None}})
    with pytest.raises(ArrangementError, match="does not read as a MIDI file"):
        arrange(path, Config())


def test_a_bank_a_track_names_and_cannot_be_read_is_reported(tmp_path: Path) -> None:
    bassline(tmp_path / "bass.mid", pulses=96)
    path = document(tmp_path / "song.yaml", {"tracks": {"bass.mid": "absent.bank"}})
    with pytest.raises(BankError):
        arrange(path, Config())
