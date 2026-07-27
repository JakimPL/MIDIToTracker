import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from trackmod.limits.compliance import Compliance

from midi2tracker import __version__
from midi2tracker.config import AUTOMATIC_SPEED, Config, load
from midi2tracker.convert import Converted, convert
from midi2tracker.tracker.format import TrackerFormat

STATED_PREFIX: Final = "Value error, "  # pydantic prepends this to the message a validator raises


def _config_argument(argv: Sequence[str] | None) -> Path | None:
    """The ``--config`` path, read before the main parser so the file can supply the flag defaults."""
    finder = argparse.ArgumentParser(add_help=False)
    finder.add_argument("--config", type=Path, default=None)
    known, _ = finder.parse_known_args(argv)
    path: Path | None = known.config
    return path


def build_parser(defaults: Config) -> argparse.ArgumentParser:
    """The command line, with every knob defaulting to what the configuration states."""
    parser = argparse.ArgumentParser(
        prog="midi2tracker",
        description="Convert a MIDI file into a tracker module",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=Path,
        help="input .mid file",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="output module (default: the input's name with the format's suffix)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="a YAML configuration file",
    )
    parser.add_argument(
        "--format",
        type=TrackerFormat,
        choices=tuple(TrackerFormat),
        default=defaults.format,
        help="the tracker format the module is written as",
    )
    parser.add_argument(
        "--compliance",
        type=Compliance,
        choices=tuple(Compliance),
        default=defaults.compliance,
        help="how strictly the module holds to the tracker the format was designed for",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=defaults.channels,
        help="how many channels the polyphony may reach",
    )
    parser.add_argument(
        "--rows-per-beat",
        type=int,
        default=defaults.rows_per_beat,
        help="rows one quarter note spans",
    )
    parser.add_argument(
        "--pattern-rows",
        type=int,
        default=defaults.pattern_rows,
        help="how tall one pattern may be",
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=defaults.speed,
        help=f"ticks per row; {AUTOMATIC_SPEED} chooses the finest the piece's tempo allows",
    )
    parser.add_argument(
        "--tempo",
        type=float,
        default=defaults.tempo,
        help="opening tempo in BPM, overriding the file",
    )
    parser.add_argument(
        "--instrument",
        type=int,
        default=defaults.instrument,
        help="the instrument slot every note plays through",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"midi2tracker {__version__}",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print what the conversion decided",
    )
    return parser


def build_config(args: argparse.Namespace, defaults: Config) -> Config:
    """The configuration one run uses: the file's values with the flags given on top.

    Rebuilding the model rather than copying it is what holds a flag to the same bounds a file's value
    answers to, so a number the format cannot carry is refused wherever it came from.

    Raises:
        ValidationError: when a flag leaves the range its field states.
    """
    return Config.model_validate(
        defaults.model_dump()
        | {
            "format": args.format,
            "compliance": args.compliance,
            "channels": args.channels,
            "rows_per_beat": args.rows_per_beat,
            "pattern_rows": args.pattern_rows,
            "speed": args.speed,
            "tempo": args.tempo,
            "instrument": args.instrument,
        }
    )


def _describe(converted: Converted, path: Path) -> str:
    """The summary one conversion prints: what it produced, and what it had to give up."""
    conversion = converted.conversion
    tempos = converted.midi.tempos
    changes = f" + {len(tempos) - 1} change(s)" if len(tempos) > 1 else ""
    lines = [
        f"{path.name}",
        f"  file size     {len(converted.module.to_bytes()):,} bytes",
        f"  patterns      {len(conversion.song.patterns)}  ({conversion.rows} rows)",
        f"  channels      {conversion.song.channels}",
        f"  notes         {len(converted.midi.notes)}",
        f"  speed         {converted.grid.speed} ticks/row  ({converted.grid.rows_per_beat} rows/beat)",
        f"  tempo         {tempos[0].beats_per_minute:.1f} BPM{changes} ->  tracker tempo {conversion.song.playback.tempo}",
    ]
    if conversion.stolen_notes:
        lines.append(f"  note          {conversion.stolen_notes} note(s) displaced another; raise --channels")
    if conversion.dropped_tempos:
        lines.append(f"  note          {len(conversion.dropped_tempos)} tempo change(s) found no free effect column")

    return "\n".join(lines)


def _detail(converted: Converted) -> str:
    """Every tempo the piece states and the row it takes effect on, for reading the grid against."""
    lines = ["  tempo map"]
    for tempo in converted.midi.tempos:
        row = converted.grid.row_of(tempo.tick)
        lines.append(f"    tick {tempo.tick:8d}  row {row:6d}  {tempo.beats_per_minute:7.2f} BPM")

    for dropped in converted.conversion.dropped_tempos:
        lines.append(f"    dropped at tick {dropped.tick}: no channel on that row had a free effect column")

    return "\n".join(lines)


def _refuse(converted: Converted) -> str:
    """The message for a piece the format will not store, listing every bound it breaks."""
    return "\n".join(["cannot write this module:", *(f"  {violation}" for violation in converted.violations)])


def _complaint(error: ErrorDetails) -> str:
    """One validation error as the command line states it: the flag it came from, or the whole setting.

    A rule spanning several fields is stated by the model itself and names no field, so its own wording
    is what the caller reads.
    """
    stated = error["msg"].removeprefix(STATED_PREFIX)
    if not error["loc"]:
        return stated

    return f"--{str(error['loc'][0]).replace('_', '-')}: {stated}"


def _reject(invalid: ValidationError) -> str:
    """The message for a setting outside what the format carries, naming the field and what it says."""
    lines = [f"  {_complaint(error)}" for error in invalid.errors()]
    return "\n".join(["these settings are outside what the format carries:", *lines])


def main(argv: Sequence[str] | None = None) -> int:
    defaults = load(_config_argument(argv))
    args = build_parser(defaults).parse_args(argv)

    try:
        config = build_config(args, defaults)
    except ValidationError as invalid:
        raise SystemExit(_reject(invalid)) from invalid

    output = args.output or args.input.with_suffix(config.target.extension)
    converted = convert(args.input, config)
    if not converted.writable:
        raise SystemExit(_refuse(converted))

    converted.save(output)
    print(_describe(converted, output))
    if args.verbose:
        print(_detail(converted))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
