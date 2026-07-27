from __future__ import annotations

from pathlib import Path

import pytest
from trackmod.trackers.it.module import ITModule
from trackmod.trackers.it.spec.identity import MAGIC_MODULE
from trackmod.trackers.xm.module import XMModule
from trackmod.trackers.xm.spec.identity import MAGIC

from midi2tracker.cli import build_parser, main
from midi2tracker.config import Config, load


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
    for heading in ("file size", "patterns", "channels", "notes", "speed", "tempo"):
        assert heading in printed


def test_the_verbose_run_reads_the_grid_against_the_tempo_map(piece: Path, tmp_path: Path, capsys) -> None:
    main([str(piece), str(tmp_path / "out.it"), "--verbose"])
    printed = capsys.readouterr().out
    assert "tempo map" in printed
    assert "BPM" in printed
