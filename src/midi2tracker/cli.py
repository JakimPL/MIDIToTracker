import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from pydantic import ValidationError
from pydantic_core import ErrorDetails
from trackmod.limits.compliance import Compliance

from midi2tracker import __version__
from midi2tracker.arrangement.error import ArrangementError
from midi2tracker.config import Config, load
from midi2tracker.convert import Converted, convert
from midi2tracker.instruments.error import BankError
from midi2tracker.midi.events import NoteEvent
from midi2tracker.settings import AUTOMATIC_SPEED, ChannelAllocation
from midi2tracker.song.report import TrackReport
from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.voices.error import AllocationError

STATED_PREFIX: Final = "Value error, "  # pydantic prepends this to the message a validator raises
SEVERAL_TRACKS: Final = 2  # the count from which a piece is worth reporting track by track
SETTING_FLAGS: Final = frozenset(
    {
        "format",
        "compliance",
        "channels",
        "allocation",
        "rows_per_beat",
        "pattern_rows",
        "speed",
        "tempo",
        "instrument",
        "bank",
        "instrument_file",
        "velocity_map",
    }
)


def _config_argument(argv: Sequence[str] | None) -> Path | None:
    """The ``--config`` path, read before the main parser so the file can supply the flag defaults."""
    finder = argparse.ArgumentParser(add_help=False)
    finder.add_argument("--config", type=Path, default=None)
    known, _ = finder.parse_known_args(argv)
    path: Path | None = known.config
    return path


def _supplied(value: object) -> str:
    """What the settings already supply for one flag, as its help line names it.

    A knob the settings leave open reads as the flag's own description alone, since there is no value
    to quote for it yet.
    """
    return "" if value is None else f"  (settings: {value})"


def build_parser(defaults: Config) -> argparse.ArgumentParser:
    """The command line, with each setting flag naming what the configuration file supplies for it.

    A setting flag holds no default of its own: left untyped it stays out of the namespace, so what a
    run states is exactly what was typed and the piece decides the rest.
    """
    parser = argparse.ArgumentParser(
        prog="midi2tracker",
        description="Convert a MIDI file, or an arrangement of several, into a tracker module",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "input",
        type=Path,
        help="a .mid file, or a .yaml arrangement naming several of them",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="output module",
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
        default=argparse.SUPPRESS,
        help=f"the tracker format the module is written as{_supplied(defaults.format)}",
    )
    parser.add_argument(
        "--compliance",
        type=Compliance,
        choices=tuple(Compliance),
        default=argparse.SUPPRESS,
        help=(
            "how strictly the module holds to the tracker the format was designed for"
            f"{_supplied(defaults.compliance)}"
        ),
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=argparse.SUPPRESS,
        help=f"how many channels one track's polyphony may reach{_supplied(defaults.channels)}",
    )
    parser.add_argument(
        "--allocation",
        type=ChannelAllocation,
        choices=tuple(ChannelAllocation),
        default=argparse.SUPPRESS,
        help=f"how the tracks of an arrangement share the channel table{_supplied(defaults.allocation)}",
    )
    parser.add_argument(
        "--rows-per-beat",
        type=int,
        default=argparse.SUPPRESS,
        help=f"rows one quarter note spans{_supplied(defaults.rows_per_beat)}",
    )
    parser.add_argument(
        "--pattern-rows",
        type=int,
        default=argparse.SUPPRESS,
        help=f"how tall one pattern may be{_supplied(defaults.pattern_rows)}",
    )
    parser.add_argument(
        "--speed",
        type=int,
        default=argparse.SUPPRESS,
        help=(
            f"ticks per row; {AUTOMATIC_SPEED} chooses the finest the piece's tempo allows"
            f"{_supplied(defaults.speed)}"
        ),
    )
    parser.add_argument(
        "--tempo",
        type=float,
        default=argparse.SUPPRESS,
        help=(
            "the one tempo in BPM the piece plays throughout; stating none follows the file's tempo map"
            f"{_supplied(defaults.tempo)}"
        ),
    )
    parser.add_argument(
        "--instrument",
        type=int,
        default=argparse.SUPPRESS,
        help=f"the slot the instruments start on{_supplied(defaults.instrument)}",
    )
    parser.add_argument(
        "--bank",
        type=Path,
        default=argparse.SUPPRESS,
        help=(
            "a bank container, or a manifest, naming the instruments the notes play through"
            f"{_supplied(defaults.bank)}"
        ),
    )
    parser.add_argument(
        "--instrument-file",
        type=Path,
        default=argparse.SUPPRESS,
        help=f"one instrument file every note plays through{_supplied(defaults.instrument_file)}",
    )
    parser.add_argument(
        "--velocity-map",
        type=Path,
        default=argparse.SUPPRESS,
        help=(
            "the measured velocity map an instrument file is read with; stating none reads velocity evenly"
            f"{_supplied(defaults.velocity_map)}"
        ),
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


def stated_settings(args: argparse.Namespace) -> dict[str, object]:
    """The settings one run was typed with, which are the flags that reached the namespace.

    Every setting flag is suppressed when it goes untyped, so what this returns is the top layer: the
    knobs a caller stated by hand, over both the configuration file and the piece's own ``settings``.
    """
    return {name: value for name, value in vars(args).items() if name in SETTING_FLAGS}


def _cost(track: TrackReport) -> str:
    """What one track gave up, as a phrase; a track that gave up nothing states nothing."""
    counted = (
        (track.stolen, "displaced"),
        (len(track.unplayable), "past the keys"),
        (len(track.silent), "unsampled"),
    )
    named = [f"{count} {reason}" for count, reason in counted if count]
    return f"  ({', '.join(named)})" if named else ""


def _tracks(converted: Converted) -> list[str]:
    """One line per track of a piece assembled from several files, since each is corrected on its own.

    A piece read from one file has its channels and its losses in the lines around this already.
    """
    tracks = converted.conversion.tracks
    if len(tracks) < SEVERAL_TRACKS:
        return []

    width = max(len(track.name) for track in tracks)
    stated = [f"  tracks        {len(tracks)}  ({converted.arrangement.allocation})"]
    stated.extend(
        f"    {track.name:<{width}}  {track.channels:2d} channel(s)  {track.notes:4d} note(s){_cost(track)}"
        for track in tracks
    )
    return stated


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
        f"  notes         {converted.arrangement.notes}",
        *_tracks(converted),
        f"  bank          {', '.join(bank.name for bank in converted.ensemble.banks)}",
        f"  instruments   {len(conversion.song.instruments)}  ({len(conversion.song.samples)} sample(s))",
        f"  speed         {converted.grid.speed} ticks/row  ({converted.grid.rows_per_beat} rows/beat)",
        f"  tempo         {tempos[0].beats_per_minute:.1f} BPM{changes} ->  tracker tempo {conversion.song.playback.tempo}",
    ]
    if conversion.stolen_notes:
        lines.append(
            f"  note          {conversion.stolen_notes} note(s) displaced another; raise --channels, or the "
            "ceiling the track states"
        )
    if conversion.dropped_tempos:
        lines.append(f"  note          {len(conversion.dropped_tempos)} tempo change(s) found no free effect column")
    if conversion.unplayable_notes:
        lines.append(
            f"  note          {len(conversion.unplayable_notes)} note(s) lie past the keys this format numbers"
        )
    if conversion.silent_notes:
        lines.append(f"  note          {len(conversion.silent_notes)} note(s) reach a key the bank leaves unsampled")

    return "\n".join(lines)


def _pitches(heading: str, notes: Sequence[NoteEvent]) -> list[str]:
    """The distinct MIDI pitches one heading covers, so a gap in the music has a name to look up."""
    if not notes:
        return []

    stated = ", ".join(str(pitch) for pitch in sorted({note.pitch for note in notes}))
    return [f"  {heading}", f"    MIDI {stated}"]


def _left_out(tracks: Sequence[TrackReport]) -> list[str]:
    """The pitches each track leaves out, under the reason they went unheard.

    Naming the track is what points at the instrument to sample more widely or the part to transpose,
    since a piece assembled from stems answers each of those in one stem at a time.
    """
    lines: list[str] = []
    for track in tracks:
        lines.extend(_pitches(f"{track.name}: past the keys this format numbers", track.unplayable))
        lines.extend(_pitches(f"{track.name}: left unsampled by the bank", track.silent))

    return lines


def _unheard(converted: Converted) -> list[str]:
    """Every tempo a track states that the module does not play, and the track that stated it."""
    return [
        f"    unheard on {unheard.track} at tick {unheard.tempo.tick}: "
        f"{unheard.tempo.beats_per_minute:.2f} BPM; name that track as the clock to follow it"
        for unheard in converted.arrangement.unheard_tempos
    ]


def _detail(converted: Converted) -> str:
    """Every tempo the piece states and the row it takes effect on, for reading the grid against."""
    conversion = converted.conversion
    lines = ["  tempo map"]
    for tempo in converted.midi.tempos:
        row = converted.grid.row_of(tempo.tick)
        lines.append(f"    tick {tempo.tick:8d}  row {row:6d}  {tempo.beats_per_minute:7.2f} BPM")

    lines.extend(_unheard(converted))
    for dropped in conversion.dropped_tempos:
        lines.append(f"    dropped at tick {dropped.tick}: no channel on that row had a free effect column")

    lines.extend(_left_out(conversion.tracks))
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
    """The message for a setting the model refuses, naming the field and what it says."""
    lines = [f"  {_complaint(error)}" for error in invalid.errors()]
    return "\n".join(["these settings cannot be used as given:", *lines])


def _graded(defaults: Config, overrides: Mapping[str, object]) -> None:
    """Hold the flags typed to their fields' bounds before a file is opened.

    The layers settle again once the piece is in hand, and this earlier grading is what lets a value the
    format cannot carry be named after the flag it was typed on.

    Raises:
        SystemExit: when a flag leaves the range its field states.
    """
    try:
        defaults.updated(overrides)
    except ValidationError as invalid:
        raise SystemExit(_reject(invalid)) from invalid


def main(argv: Sequence[str] | None = None) -> int:
    defaults = load(_config_argument(argv))
    args = build_parser(defaults).parse_args(argv)
    overrides = stated_settings(args)
    _graded(defaults, overrides)

    output = args.output
    try:
        converted = convert(args.input, defaults, overrides)
    except ArrangementError as unreadable:
        raise SystemExit(f"cannot read this piece:\n  {unreadable}") from unreadable
    except BankError as unreadable:
        raise SystemExit(f"cannot assemble the bank:\n  {unreadable}") from unreadable
    except AllocationError as unplayable:
        raise SystemExit(f"cannot lay this piece out:\n  {unplayable}") from unplayable

    if not converted.writable:
        raise SystemExit(_refuse(converted))

    converted.save(output)
    print(_describe(converted, output))
    if args.verbose:
        print(_detail(converted))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
