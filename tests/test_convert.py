from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from trackmod.core.instruments.transfer import extract
from trackmod.core.notes.command import NoteCommand
from trackmod.core.songs.song import Song
from trackmod.limits.compliance import Compliance
from trackmod.spec.grid import EMPTY
from trackmod.trackers.it.module import ITModule
from trackmod.trackers.xm.module import XMModule

from midi2tracker.config import Config
from midi2tracker.convert import convert, row_grid
from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.manifest import MANIFEST_VERSION
from midi2tracker.instruments.source import load_unit
from midi2tracker.instruments.velocity import VELOCITY_COUNT
from midi2tracker.midi.parser import parse_midi
from midi2tracker.timing.speed import speed_bound
from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.tracker.target import TrackerTarget
from tests.conftest import (
    SAMPLE_FRAMES,
    instrument_file,
    lift,
    pedal,
    press,
    velocity_map_file,
    write_midi,
)


def settings(target: TrackerTarget, **stated: object) -> Config:
    """A configuration writing through one format, with whatever a test states on top."""
    return Config(format=target.format, compliance=target.compliance, **stated)


def reread(path: Path, target: TrackerTarget) -> Song:
    """The song a written module gives back, read by the parser of the format it was written as."""
    match target.format:
        case TrackerFormat.IT:
            return ITModule.load(path).song
        case TrackerFormat.XM:
            return XMModule.load(path).song


def test_a_real_file_converts_into_a_writable_module(piece: Path, target: TrackerTarget) -> None:
    converted = convert(piece, settings(target))
    assert converted.writable
    assert converted.violations == ()
    assert converted.module.size().total == len(converted.module.to_bytes())


def test_the_module_reads_back_as_the_song_it_was_written_from(
    piece: Path,
    tmp_path: Path,
    target: TrackerTarget,
) -> None:
    # Parsing with a decoder this converter did not write is the check that the bytes mean what the
    # model says: the notes, the channel count and the clock all have to survive the trip.
    converted = convert(piece, settings(target))
    recovered = reread(converted.save(tmp_path / f"out{target.extension}"), target)
    assert recovered.channels == converted.conversion.song.channels
    assert recovered.rows == converted.conversion.rows
    assert recovered.playback == converted.conversion.song.playback


def test_every_note_in_the_file_reaches_the_grid(piece: Path, target: TrackerTarget) -> None:
    # Each note fills one cell where it starts, and most fill a second where they release, so the note
    # column holds at least as many entries as the file has notes.
    converted = convert(piece, settings(target))
    placed = sum(int((pattern.note != EMPTY).sum()) for pattern in converted.conversion.song.patterns)
    assert placed >= len(converted.midi.notes)
    assert converted.conversion.stolen_notes == 0


def test_the_file_is_written_where_it_was_asked_for(piece: Path, tmp_path: Path, target: TrackerTarget) -> None:
    output = tmp_path / f"out{target.extension}"
    convert(piece, settings(target)).save(output)
    assert reread(output, target).channels > 0


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


def test_the_chosen_speed_never_leaves_the_addressable_range(piece: Path, target: TrackerTarget) -> None:
    for rows_per_beat in (1, 2, 4, 8, 15, 32):
        grid = row_grid(parse_midi(piece), settings(target, rows_per_beat=rows_per_beat))
        assert speed_bound(target).contains(grid.speed)


def test_the_instrument_slot_reserves_the_slots_below_it(piece: Path, target: TrackerTarget) -> None:
    converted = convert(piece, settings(target, instrument=5))
    instruments = converted.conversion.song.instruments
    assert len(instruments) == 5
    assert all(assignment is None for instrument in instruments[:4] for assignment in instrument.keymap)
    assert converted.writable


def test_a_conversion_naming_no_instrument_still_writes_the_slot_to_fill_in(piece: Path, target: TrackerTarget) -> None:
    song = convert(piece, settings(target)).conversion.song
    assert len(song.instruments) == 1
    assert song.samples[0].frames == 0


def test_an_instrument_file_is_what_the_notes_play_through(piece: Path, tmp_path: Path, target: TrackerTarget) -> None:
    source = instrument_file(tmp_path / "piano.it")
    converted = convert(piece, settings(target, instrument_file=source))
    song = converted.conversion.song
    assert converted.writable
    assert len(song.samples) == 1 and song.samples[0].frames == SAMPLE_FRAMES


def test_the_instrument_reaches_the_written_file_verbatim(piece: Path, tmp_path: Path) -> None:
    # Taking an instrument as it was produced is the contract, so the keymap and every sample setting
    # have to survive the trip out to disk and back.
    source = load_unit(instrument_file(tmp_path / "piano.it"), 0)
    output = convert(piece, Config(instrument_file=tmp_path / "piano.it")).save(tmp_path / "out.it")
    recovered = extract(ITModule.load(output).song, 0)
    assert recovered.instrument.keymap == source.instrument.keymap
    assert recovered.samples == source.samples


def test_a_velocity_map_beside_the_instrument_decides_the_volume_column(piece: Path, tmp_path: Path) -> None:
    instrument_file(tmp_path / "piano.it")
    velocity_map_file(tmp_path / "velocity_map.json", [9] * VELOCITY_COUNT)
    converted = convert(piece, Config(instrument_file=tmp_path / "piano.it"))
    volumes = {int(volume) for pattern in converted.conversion.song.patterns for volume in pattern.volume.flat}
    assert 9 in volumes


def test_a_note_the_instrument_was_never_sampled_over_is_reported(tmp_path: Path, target: TrackerTarget) -> None:
    path = write_midi(tmp_path / "wide.mid", [press(60, 0), lift(60, 96), press(24, 96), lift(24, 192)])
    converted = convert(path, settings(target, instrument_file=instrument_file(tmp_path / "piano.it")))
    assert [note.pitch for note in converted.conversion.silent_notes] == [24]
    assert converted.conversion.unplayable_notes == ()
    assert converted.writable


def test_a_note_past_the_keys_the_format_numbers_is_reported(tmp_path: Path) -> None:
    # FastTracker 2 stops eight octaves up, so the same piece states every note as Impulse Tracker and
    # names one of them as out of reach as FastTracker 2.
    path = write_midi(tmp_path / "high.mid", [press(60, 0), lift(60, 96), press(120, 96), lift(120, 192)])
    fast = convert(path, Config(format=TrackerFormat.XM))
    impulse = convert(path, Config(format=TrackerFormat.IT))
    assert [note.pitch for note in fast.conversion.unplayable_notes] == [120]
    assert impulse.conversion.unplayable_notes == ()


def test_a_bank_manifest_puts_each_layer_on_a_slot_of_its_own(piece: Path, tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    instrument_file(tmp_path / "loud.it", name="Loud")
    manifest = tmp_path / "bank.json"
    manifest.write_text(
        json.dumps(
            {
                "version": MANIFEST_VERSION,
                "name": "Layered",
                "layers": [
                    {"source": {"file": "quiet.it"}, "select": {"velocity": {"low": 0, "high": 63}}},
                    {"source": {"file": "loud.it"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    converted = convert(piece, Config(bank=manifest))
    song = converted.conversion.song
    assert [instrument.name for instrument in song.instruments] == ["Quiet 0", "Loud 0"]
    assert len(song.samples) == 2
    assert converted.writable


def test_an_instrument_the_settings_name_and_cannot_be_read_is_reported(piece: Path, tmp_path: Path) -> None:
    with pytest.raises(BankError):
        convert(piece, Config(instrument_file=tmp_path / "absent.it"))


def test_naming_both_a_bank_and_an_instrument_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="state one"):
        Config(bank=tmp_path / "bank.json", instrument_file=tmp_path / "piano.it")


def test_a_velocity_map_with_no_instrument_file_to_read_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="which file"):
        Config(velocity_map=tmp_path / "velocity_map.json")


def test_a_channel_ceiling_costs_notes_rather_than_the_conversion(piece: Path, target: TrackerTarget) -> None:
    converted = convert(piece, settings(target, channels=1))
    assert converted.conversion.song.channels <= 2  # rounded up to a stereo pair
    assert converted.writable


def test_a_long_piece_at_a_short_pattern_height_still_fits_the_order_table(
    tmp_path: Path,
    target: TrackerTarget,
) -> None:
    # A height the piece cannot be cut at gives way, where the pre-migration writer crashed building an
    # order table longer than the format names.
    messages = []
    for index in range(1200):
        messages.extend([press(60, index * 96), lift(60, index * 96 + 48)])

    path = write_midi(tmp_path / "long.mid", messages)
    converted = convert(path, settings(target, pattern_rows=8, rows_per_beat=4))
    patterns = converted.conversion.song.patterns
    assert len(patterns) <= target.max_patterns
    assert max(pattern.rows for pattern in patterns) <= target.max_rows
    assert converted.writable


def test_the_sustain_pedal_reaches_the_grid_as_a_longer_note(tmp_path: Path, target: TrackerTarget) -> None:
    path = write_midi(
        tmp_path / "pedal.mid",
        [press(60, 0), pedal(127, 8), lift(60, 24), pedal(0, 384)],
    )
    converted = convert(path, settings(target, rows_per_beat=4))
    grid = converted.grid
    patterns = converted.conversion.song.patterns
    assert patterns[0].cell(0, 0).note == target.key(60)
    assert patterns[0].cell(grid.row_of(384), 0).note == NoteCommand.OFF


def test_an_empty_file_converts_into_a_module_that_plays_nothing(tmp_path: Path, target: TrackerTarget) -> None:
    path = write_midi(tmp_path / "empty.mid", [press(60, 0), lift(60, 0)])
    converted = convert(path, settings(target))
    assert converted.writable
    assert converted.conversion.song.rows >= target.min_rows


def test_the_module_is_canonical_by_default(piece: Path) -> None:
    # Canonical is what makes the file open in the tracker the format was designed for, not only in a
    # modern player.
    assert convert(piece, Config()).module.limits.compliance is Compliance.CANONICAL


def test_impulse_tracker_is_the_default_format(piece: Path) -> None:
    assert convert(piece, Config()).module.extension == ".it"
