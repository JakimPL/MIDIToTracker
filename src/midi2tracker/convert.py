from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from trackmod.limits.violation import Violation
from trackmod.module.protocol import TrackerModule

from midi2tracker.arrangement.build import arrange
from midi2tracker.arrangement.piece import Arrangement
from midi2tracker.config import Config
from midi2tracker.instruments.ensemble import Ensemble
from midi2tracker.midi.events import MidiSong
from midi2tracker.settings import NO_OVERRIDES
from midi2tracker.song.builder import Conversion, build_song
from midi2tracker.song.layout import Layout
from midi2tracker.timing.grid import RowGrid
from midi2tracker.timing.speed import select_speed
from midi2tracker.voices.allocation import allocate


@dataclass(frozen=True)
class Converted:
    """A converted piece: the module, the arrangement it was assembled from, and what it cost."""

    module: TrackerModule
    arrangement: Arrangement
    grid: RowGrid
    conversion: Conversion

    @property
    def midi(self) -> MidiSong:
        """The track the piece keeps time by, which is the clock the grid was built against."""
        return self.arrangement.timing

    @property
    def ensemble(self) -> Ensemble:
        """The instrument table the module states, over every bank the piece plays through."""
        return self.arrangement.ensemble

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
    speed = (
        select_speed(midi.fastest, config.rows_per_beat, target=config.target)
        if config.automatic_speed
        else config.speed
    )
    return RowGrid(pulses_per_beat=midi.pulses_per_beat, rows_per_beat=config.rows_per_beat, speed=speed)


def convert(path: Path | str, config: Config, overrides: Mapping[str, object] = NO_OVERRIDES) -> Converted:
    """Convert the piece at ``path`` into a module under ``config``, with ``overrides`` on top.

    ``config`` is the bottom layer, what the configuration file states, and ``overrides`` the knobs the
    command line was typed with. The piece settles the two with its own ``settings`` in between, and the
    module is written from what they settled on, so every stage here reads one answer per knob.

    Raises:
        ArrangementError: when the arrangement, a MIDI file it names, or the settings it states cannot
            be read.
        BankError: when the instruments the piece names cannot be read.
        AllocationError: when the piece reaches more channels than the format plays.
    """
    arrangement = arrange(Path(path), config, overrides)
    settled = arrangement.config
    target = settled.target
    grid = row_grid(arrangement.timing, settled)
    allocation = allocate(arrangement.tracks, grid, allocation=settled.allocation, target=target)
    layout = Layout(height=settled.pattern_rows, name=arrangement.name)
    conversion = build_song(arrangement, allocation, grid, layout, target=target)
    return Converted(
        module=target.bind(conversion.song),
        arrangement=arrangement,
        grid=grid,
        conversion=conversion,
    )
