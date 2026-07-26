"""One MIDI file to one tracker module, end to end.

This is the seam the command line and any other caller share: give it a path and a configuration, and it
parses, chooses the clock, allocates the voices, builds the song and binds it to the format. Everything it
had to give up along the way travels with the result rather than being printed from inside, so a caller
decides how to report it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trackmod.limits.compliance import Compliance
from trackmod.limits.violation import Violation
from trackmod.xm.module import XMModule
from trackmod.xm.settings import XMSettings

from midi2xm.config import Config
from midi2xm.midi.events import MidiSong
from midi2xm.midi.parser import parse_midi
from midi2xm.song.builder import Conversion, build_song
from midi2xm.song.layout import Layout
from midi2xm.spec import TRACKER_NAME
from midi2xm.timing.grid import RowGrid
from midi2xm.timing.speed import select_speed
from midi2xm.voices.allocation import allocate


@dataclass(frozen=True)
class Converted:
    """A converted piece: the module, the clock it plays on, and what the conversion cost."""

    module: XMModule
    midi: MidiSong
    grid: RowGrid
    conversion: Conversion

    @property
    def violations(self) -> tuple[Violation, ...]:
        """Every bound the module breaks, empty when it can be written."""
        return self.module.violations()

    @property
    def writable(self) -> bool:
        """Whether the module writes without raising."""
        return not self.violations

    def save(self, path: Path) -> Path:
        """Write the module and return where it went."""
        self.module.save(path)
        return path


def row_grid(midi: MidiSong, config: Config) -> RowGrid:
    """The clock a piece is placed on: its own resolution, the row rate asked for, and a speed."""
    speed = select_speed(midi.fastest, config.rows_per_beat) if config.automatic_speed else config.speed
    return RowGrid(pulses_per_beat=midi.pulses_per_beat, rows_per_beat=config.rows_per_beat, speed=speed)


def convert(path: Path | str, config: Config, *, compliance: Compliance = Compliance.CANONICAL) -> Converted:
    """Convert the MIDI file at ``path`` into a module under ``config``."""
    parsed = parse_midi(path)
    midi = parsed if config.tempo is None else parsed.starting_at(config.tempo)
    grid = row_grid(midi, config)
    allocation = allocate(midi, grid, channels=config.channels)
    layout = Layout(height=config.pattern_rows, slot=config.slot, name=Path(path).stem)
    conversion = build_song(midi, allocation, grid, layout)
    module = XMModule.from_song(conversion.song, compliance=compliance, settings=XMSettings(tracker=TRACKER_NAME))
    return Converted(module=module, midi=midi, grid=grid, conversion=conversion)
