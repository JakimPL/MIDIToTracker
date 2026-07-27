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
from tests.conftest import instrument_file, lift, press, write_midi


def test_the_output_defaults_to_the_input_with_the_format_suffix(piece: Path, tmp_path: Path) -> None:
    source = tmp_path / "song.mid"
    source.write_bytes(piece.read_bytes())
    assert main([str(source)]) == 0
    assert (tmp_path / "song.it").read_bytes()[: len(MAGIC_MODULE)] == MAGIC_MODULE


def test_the_format_asked_for_decides_the_suffix_and_the_bytes(piece: Path, tmp_path: Path) -> None:
    source = tmp_path / "song.mid"
    source.write_bytes(piece.read_bytes())
    assert main([str(source), "--format", "xm"]) == 0
    assert (tmp_path / "song.xm").read_bytes()[: len(MAGIC)] == MAGIC


def test_an_explicit_output_path_is_honoured(piece: Path, tmp_path: Path) -> None:
    output = tmp_path / "elsewhere.it"
    assert main([str(piece), str(output)]) == 0
    assert ITModule.load(output).song.channels > 0


def test_a_config_file_supplies_the_defaults_the_flags_override(tmp_path: Path) -> None:
    # The configuration is read before the parser is built, so a file's values are what the flags start
    # from rather than being loaded afterwards and overwritten by them.
    config = tmp_path / "custom.yaml"
    config.write_text("channels: 7\nrows_per_beat: 9\ninstrument: 3\nformat: xm\n", encoding="utf-8")
    parsed = build_parser(load(config)).parse_args(["in.mid", "--config", str(config)])
    assert (parsed.channels, parsed.rows_per_beat, parsed.instrument) == (7, 9, 3)
    assert parsed.format == "xm"


def test_a_flag_wins_over_the_configuration_it_defaults_from(tmp_path: Path) -> None:
    config = tmp_path / "custom.yaml"
    config.write_text("channels: 7\n", encoding="utf-8")
    parsed = build_parser(load(config)).parse_args(["in.mid", "--config", str(config), "--channels", "12"])
    assert parsed.channels == 12


def test_the_flags_reach_the_file_that_is_written(piece: Path, tmp_path: Path) -> None:
    output = tmp_path / "out.xm"
    arguments = [str(piece), str(output), "--format", "xm", "--speed", "4", "--rows-per-beat", "8", "--instrument", "2"]
    assert main(arguments) == 0
    song = XMModule.load(output).song
    assert song.playback.speed == 4
    assert len(song.instruments) == 2


def test_a_configuration_the_format_refuses_is_reported_at_the_parser(piece: Path) -> None:
    # Every bound is the format's, so a value outside one is refused where it is given rather than
    # written into a field too small for it.
    with pytest.raises(SystemExit):
        main([str(piece), "--channels", "0"])


def test_a_count_one_format_carries_and_the_other_refuses_follows_the_format(piece: Path, tmp_path: Path) -> None:
    # Impulse Tracker plays twice the channels FastTracker 2 does, so the same number is a module in one
    # format and a refusal in the other.
    assert main([str(piece), str(tmp_path / "wide.it"), "--channels", "64"]) == 0
    with pytest.raises(SystemExit):
        main([str(piece), str(tmp_path / "wide.xm"), "--format", "xm", "--channels", "64"])


def test_a_setting_the_whole_model_refuses_is_named_in_the_message(piece: Path, capsys) -> None:
    # The rule spans the format and the count, so it is the model that states it and the message carries
    # its own wording rather than a flag's.
    with pytest.raises(SystemExit) as refused:
        main([str(piece), "--format", "xm", "--channels", "64"])

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
