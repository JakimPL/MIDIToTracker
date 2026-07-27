from __future__ import annotations

from pathlib import Path

import pytest
from trackmod.trackers.xm.module import XMModule
from trackmod.trackers.xm.spec.identity import MAGIC

from midi2tracker.cli import build_parser, main
from midi2tracker.config import Config, load


def test_the_output_defaults_to_the_input_with_the_format_suffix(piece: Path, tmp_path: Path) -> None:
    source = tmp_path / "song.mid"
    source.write_bytes(piece.read_bytes())
    assert main([str(source)]) == 0
    assert (tmp_path / "song.xm").read_bytes()[: len(MAGIC)] == MAGIC


def test_an_explicit_output_path_is_honoured(piece: Path, tmp_path: Path) -> None:
    output = tmp_path / "elsewhere.xm"
    assert main([str(piece), str(output)]) == 0
    assert XMModule.load(output).song.channels > 0


def test_a_config_file_supplies_the_defaults_the_flags_override(tmp_path: Path) -> None:
    # The configuration is read before the parser is built, so a file's values are what the flags start
    # from rather than being loaded afterwards and overwritten by them.
    config = tmp_path / "custom.yaml"
    config.write_text("channels: 7\nrows_per_beat: 9\ninstrument: 3\n", encoding="utf-8")
    parsed = build_parser(load(config)).parse_args(["in.mid", "--config", str(config)])
    assert (parsed.channels, parsed.rows_per_beat, parsed.instrument) == (7, 9, 3)


def test_a_flag_wins_over_the_configuration_it_defaults_from(tmp_path: Path) -> None:
    config = tmp_path / "custom.yaml"
    config.write_text("channels: 7\n", encoding="utf-8")
    parsed = build_parser(load(config)).parse_args(["in.mid", "--config", str(config), "--channels", "12"])
    assert parsed.channels == 12


def test_the_flags_reach_the_file_that_is_written(piece: Path, tmp_path: Path) -> None:
    output = tmp_path / "out.xm"
    assert main([str(piece), str(output), "--speed", "4", "--rows-per-beat", "8", "--instrument", "2"]) == 0
    song = XMModule.load(output).song
    assert song.playback.speed == 4
    assert len(song.instruments) == 2


def test_a_configuration_the_format_refuses_is_reported_at_the_parser(piece: Path) -> None:
    # Every bound is the format's, so a value outside one is refused where it is given rather than
    # written into a field too small for it.
    with pytest.raises(SystemExit):
        main([str(piece), "--channels", "0"])


def test_an_unreadable_speed_is_refused() -> None:
    with pytest.raises(ValueError):
        Config(speed=64)  # a row divided into more ticks than a note delay can name


def test_the_summary_names_what_the_conversion_produced(piece: Path, tmp_path: Path, capsys) -> None:
    main([str(piece), str(tmp_path / "out.xm")])
    printed = capsys.readouterr().out
    for heading in ("file size", "patterns", "channels", "notes", "speed", "tempo"):
        assert heading in printed
