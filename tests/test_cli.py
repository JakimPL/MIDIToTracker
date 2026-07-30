from __future__ import annotations

import json
from pathlib import Path

import pytest
from trackmod.trackers.it.module import ITModule
from trackmod.trackers.it.spec.identity import MAGIC_MODULE
from trackmod.trackers.xm.module import XMModule
from trackmod.trackers.xm.spec.identity import MAGIC

from midi2tracker.cli import build_parser, main
from midi2tracker.config import Config, load
from midi2tracker.instruments.manifest import MANIFEST_VERSION
from midi2tracker.settings import ChannelAllocation
from tests.conftest import (
    instrument_file,
    lift,
    press,
    standalone_instrument,
    tempo,
    write_midi,
)

STEMS = ("bass.mid", "lead.mid", "pad.mid")


def test_where_the_module_goes_is_stated_rather_than_derived(piece: Path) -> None:
    # A piece may be assembled from several files under a name of its own, so where it is written is the
    # caller's to say.
    with pytest.raises(SystemExit):
        main([str(piece)])


def test_the_format_asked_for_decides_the_bytes_that_are_written(piece: Path, tmp_path: Path) -> None:
    impulse = tmp_path / "song.it"
    fast = tmp_path / "song.xm"
    assert main([str(piece), str(impulse)]) == 0
    assert main([str(piece), str(fast), "--format", "xm"]) == 0
    assert impulse.read_bytes()[: len(MAGIC_MODULE)] == MAGIC_MODULE
    assert fast.read_bytes()[: len(MAGIC)] == MAGIC


def test_an_explicit_output_path_is_honoured(piece: Path, tmp_path: Path) -> None:
    output = tmp_path / "elsewhere.it"
    assert main([str(piece), str(output)]) == 0
    assert ITModule.load(output).song.channels > 0


def test_a_config_file_supplies_the_defaults_the_flags_override(tmp_path: Path) -> None:
    # The configuration is read before the parser is built, so a file's values are what the flags start
    # from rather than being loaded afterwards and overwritten by them.
    config = tmp_path / "custom.yaml"
    config.write_text(
        "channels: 7\nrows_per_beat: 9\ninstrument: 3\nformat: xm\nallocation: packed\n",
        encoding="utf-8",
    )
    parsed = build_parser(load(config)).parse_args(["in.mid", "out.xm", "--config", str(config)])
    assert (parsed.channels, parsed.rows_per_beat, parsed.instrument) == (7, 9, 3)
    assert parsed.format == "xm"
    assert parsed.allocation is ChannelAllocation.PACKED


def test_a_flag_wins_over_the_configuration_it_defaults_from(tmp_path: Path) -> None:
    config = tmp_path / "custom.yaml"
    config.write_text("channels: 7\nallocation: packed\n", encoding="utf-8")
    arguments = ["in.mid", "out.it", "--config", str(config), "--channels", "12", "--allocation", "separated"]
    parsed = build_parser(load(config)).parse_args(arguments)
    assert parsed.channels == 12
    assert parsed.allocation is ChannelAllocation.SEPARATED


def test_the_flags_reach_the_file_that_is_written(piece: Path, tmp_path: Path) -> None:
    output = tmp_path / "out.xm"
    arguments = [str(piece), str(output), "--format", "xm", "--speed", "4", "--rows-per-beat", "8", "--instrument", "2"]
    assert main(arguments) == 0
    song = XMModule.load(output).song
    assert song.playback.speed == 4
    assert len(song.instruments) == 2


def test_a_configuration_the_format_refuses_is_reported_at_the_parser(piece: Path, tmp_path: Path) -> None:
    # Every bound is the format's, so a value outside one is refused where it is given rather than
    # written into a field too small for it.
    with pytest.raises(SystemExit):
        main([str(piece), str(tmp_path / "out.it"), "--channels", "0"])


def test_a_count_one_format_carries_and_the_other_refuses_follows_the_format(piece: Path, tmp_path: Path) -> None:
    # Impulse Tracker plays twice the channels FastTracker 2 does, so the same number is a module in one
    # format and a refusal in the other.
    assert main([str(piece), str(tmp_path / "wide.it"), "--channels", "64"]) == 0
    with pytest.raises(SystemExit):
        main([str(piece), str(tmp_path / "wide.xm"), "--format", "xm", "--channels", "64"])


def test_a_setting_the_whole_model_refuses_is_named_in_the_message(piece: Path, tmp_path: Path) -> None:
    # The rule spans the format and the count, so it is the model that states it and the message carries
    # its own wording rather than a flag's.
    with pytest.raises(SystemExit) as refused:
        main([str(piece), str(tmp_path / "out.xm"), "--format", "xm", "--channels", "64"])

    assert "channels 64 is above 32" in str(refused.value)


def test_an_unreadable_speed_is_refused() -> None:
    with pytest.raises(ValueError):
        Config(speed=64)  # a row divided into more ticks than a note delay can name


def test_the_summary_names_what_the_conversion_produced(piece: Path, tmp_path: Path, capsys) -> None:
    main([str(piece), str(tmp_path / "out.it")])
    printed = capsys.readouterr().out
    for heading in ("file size", "patterns", "channels", "notes", "bank", "instruments", "speed", "tempo"):
        assert heading in printed


def test_the_verbose_run_reads_the_grid_against_the_tempo_map(piece: Path, tmp_path: Path, capsys) -> None:
    main([str(piece), str(tmp_path / "out.it"), "--verbose"])
    printed = capsys.readouterr().out
    assert "tempo map" in printed
    assert "BPM" in printed


def test_an_instrument_file_reaches_the_module_the_flag_writes(piece: Path, tmp_path: Path, capsys) -> None:
    source = instrument_file(tmp_path / "piano.it")
    output = tmp_path / "out.it"
    assert main([str(piece), str(output), "--instrument-file", str(source)]) == 0
    assert ITModule.load(output).song.samples[0].frames > 0
    assert "instruments   1" in capsys.readouterr().out


@pytest.mark.parametrize("suffix", (".iti", ".xi"))
def test_an_instrument_stored_on_its_own_reaches_the_module_the_flag_writes(
    piece: Path,
    tmp_path: Path,
    capsys,
    suffix: str,
) -> None:
    source = standalone_instrument(tmp_path / f"piano{suffix}", name="Grand")
    output = tmp_path / "out.it"
    assert main([str(piece), str(output), "--instrument-file", str(source)]) == 0
    assert ITModule.load(output).song.samples[0].frames > 0
    assert "bank          Grand" in capsys.readouterr().out


def test_a_bank_manifest_reaches_the_module_the_flag_writes(piece: Path, tmp_path: Path, capsys) -> None:
    instrument_file(tmp_path / "piano.it")
    manifest = tmp_path / "bank.json"
    manifest.write_text(
        json.dumps({"version": MANIFEST_VERSION, "name": "One", "layers": [{"source": {"file": "piano.it"}}]}),
        encoding="utf-8",
    )
    output = tmp_path / "out.it"
    assert main([str(piece), str(output), "--bank", str(manifest)]) == 0
    assert ITModule.load(output).song.instruments[0].name == "Sampled 0"
    assert "bank          One" in capsys.readouterr().out


def test_an_instrument_that_cannot_be_read_is_reported_rather_than_raised(piece: Path, tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="cannot assemble the bank"):
        main([str(piece), str(tmp_path / "out.it"), "--instrument-file", str(tmp_path / "absent.it")])


def test_a_midi_file_that_cannot_be_read_is_reported_rather_than_raised(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="cannot read this piece"):
        main([str(tmp_path / "absent.mid"), str(tmp_path / "out.it")])


def test_a_piece_spreading_past_the_format_is_reported_before_anything_is_written(tmp_path: Path) -> None:
    # Two stems of twenty voices each reach forty channels where FastTracker 2 plays thirty-two, and the
    # width follows from the piece rather than from any one setting, so it is caught where it is derived.
    chord = [message for pitch in range(48, 68) for message in (press(pitch, 0), lift(pitch, 96))]
    for stem in ("bass.mid", "brass.mid"):
        write_midi(tmp_path / stem, chord)

    arrangement = tmp_path / "song.yaml"
    arrangement.write_text("tracks:\n  bass.mid:\n  brass.mid:\n", encoding="utf-8")
    output = tmp_path / "out.xm"
    with pytest.raises(SystemExit, match="cannot lay this piece out"):
        main([str(arrangement), str(output), "--format", "xm", "--channels", "20"])

    assert not output.exists()


def test_an_arrangement_of_several_files_writes_one_module(tmp_path: Path, capsys) -> None:
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96)])
    arrangement = tmp_path / "song.yaml"
    arrangement.write_text("tracks:\n  bass.mid:\n  lead.mid:\n", encoding="utf-8")
    output = tmp_path / "out.it"
    assert main([str(arrangement), str(output)]) == 0
    assert ITModule.load(output).song.channels > 0
    assert "notes         2" in capsys.readouterr().out


def test_the_summary_names_every_track_of_a_piece_assembled_from_several_files(tmp_path: Path, capsys) -> None:
    # Each loss is corrected in one stem, so the account is stated stem by stem rather than only summed.
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 192), press(50, 0), lift(50, 192)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96)])
    arrangement = tmp_path / "song.yaml"
    arrangement.write_text("tracks:\n  bass.mid:\n    channels: 1\n  lead.mid:\n", encoding="utf-8")
    assert main([str(arrangement), str(tmp_path / "out.it")]) == 0

    printed = capsys.readouterr().out
    assert "tracks        2  (separated)" in printed
    assert "bass" in printed and "lead" in printed
    assert "1 displaced" in printed


def test_a_piece_read_from_one_file_states_no_track_breakdown(piece: Path, tmp_path: Path, capsys) -> None:
    assert main([str(piece), str(tmp_path / "out.it")]) == 0
    assert "tracks " not in capsys.readouterr().out


def in_turn(tmp_path: Path, stated: str) -> Path:
    """Three stems taking their turn, so keeping them apart costs three channels and packing costs one."""
    for index, stem in enumerate(STEMS):
        write_midi(tmp_path / stem, [press(48 + index, index * 192), lift(48 + index, index * 192 + 96)])

    arrangement = tmp_path / "song.yaml"
    arrangement.write_text(stated + "".join(f"  {stem}:\n" for stem in STEMS), encoding="utf-8")
    return arrangement


def test_packing_the_tracks_reaches_a_narrower_module_than_keeping_them_apart(tmp_path: Path, capsys) -> None:
    stated, written = {}, {}
    arrangement = in_turn(tmp_path, "tracks:\n")
    for allocation in ("separated", "packed"):
        output = tmp_path / f"{allocation}.it"
        assert main([str(arrangement), str(output), "--allocation", allocation]) == 0
        stated[allocation] = capsys.readouterr().out
        written[allocation] = ITModule.load(output).song.channels

    assert "channels      4" in stated["separated"]
    assert "channels      2" in stated["packed"]
    assert written == {"separated": 4, "packed": 2}


def test_the_allocation_a_document_states_is_the_one_the_flag_defaults_to(tmp_path: Path, capsys) -> None:
    # The document describes the piece and the flag the run, so a piece stating how it is laid out keeps
    # that layout wherever it is converted from.
    arrangement = in_turn(tmp_path, "settings:\n  allocation: packed\ntracks:\n")
    assert main([str(arrangement), str(tmp_path / "out.it"), "--allocation", "separated"]) == 0

    printed = capsys.readouterr().out
    assert "tracks        3  (packed)" in printed
    assert "channels      2" in printed


def test_a_tempo_the_piece_does_not_follow_is_named_by_the_verbose_run(tmp_path: Path, capsys) -> None:
    write_midi(tmp_path / "bass.mid", [press(48, 0), lift(48, 96), tempo(120.0, 0)])
    write_midi(tmp_path / "lead.mid", [press(72, 0), lift(72, 96), tempo(90.0, 0)])
    arrangement = tmp_path / "song.yaml"
    arrangement.write_text("tracks:\n  bass.mid:\n  lead.mid:\n", encoding="utf-8")
    assert main([str(arrangement), str(tmp_path / "out.it"), "--verbose"]) == 0

    printed = capsys.readouterr().out
    assert "unheard on lead" in printed
    assert "90.00 BPM" in printed


def test_the_notes_a_run_leaves_out_are_named_in_the_summary(tmp_path: Path, capsys) -> None:
    source = instrument_file(tmp_path / "piano.it")
    path = write_midi(tmp_path / "wide.mid", [press(60, 0), lift(60, 96), press(24, 96), lift(24, 192)])
    assert main([str(path), str(tmp_path / "out.it"), "--instrument-file", str(source), "--verbose"]) == 0
    printed = capsys.readouterr().out
    assert "the bank leaves unsampled" in printed
    assert "MIDI 24" in printed


def test_an_instrument_a_format_cannot_store_is_reported_before_anything_is_written(
    piece: Path,
    tmp_path: Path,
) -> None:
    # FastTracker 2 has no per-sample gain field, so an instrument staged with one belongs to a bank
    # produced for the format it will be played in; folding the gain into the waveform on the way across
    # would re-quantise it and undo the staging deliberately.
    source = instrument_file(tmp_path / "piano.it", gain=32)
    output = tmp_path / "out.xm"
    with pytest.raises(SystemExit, match="cannot write this module"):
        main([str(piece), str(output), "--format", "xm", "--instrument-file", str(source)])

    assert not output.exists()


def test_a_note_past_the_keys_the_format_numbers_is_named_in_the_summary(tmp_path: Path, capsys) -> None:
    path = write_midi(tmp_path / "high.mid", [press(120, 0), lift(120, 96)])
    assert main([str(path), str(tmp_path / "out.xm"), "--format", "xm", "--verbose"]) == 0
    printed = capsys.readouterr().out
    assert "past the keys this format numbers" in printed
    assert "MIDI 120" in printed
