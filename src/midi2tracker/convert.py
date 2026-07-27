from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trackmod.limits.violation import Violation
from trackmod.module.protocol import TrackerModule

from midi2tracker.config import Config
from midi2tracker.instruments.bank import Bank
from midi2tracker.midi.events import MidiSong
from midi2tracker.midi.parser import parse_midi
from midi2tracker.song.builder import Conversion, build_song
from midi2tracker.song.layout import Layout
from midi2tracker.timing.grid import RowGrid
from midi2tracker.timing.speed import select_speed
from midi2tracker.voices.allocation import allocate


@dataclass(frozen=True)
class Converted:
    """A converted piece: the module, the clock it plays on, and what the conversion cost."""

    module: TrackerModule
    midi: MidiSong
    grid: RowGrid
    bank: Bank
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
    speed = (
        select_speed(midi.fastest, config.rows_per_beat, target=config.target)
        if config.automatic_speed
        else config.speed
    )
    return RowGrid(pulses_per_beat=midi.pulses_per_beat, rows_per_beat=config.rows_per_beat, speed=speed)


def instrument_bank(config: Config) -> Bank:
    """The instruments a conversion plays through, from whichever of the settings names them.

    Raises:
        BankError: when the manifest, an instrument, or a velocity map cannot be read.
    """
    if config.bank is not None:
        return Bank.from_manifest(config.bank, offset=config.slot)

    if config.instrument_file is not None:
        return Bank.from_instrument(config.instrument_file, velocity_map=config.velocity_map, offset=config.slot)

    return Bank.placeholder(offset=config.slot)


def convert(path: Path | str, config: Config) -> Converted:
    """Convert the MIDI file at ``path`` into a module under ``config``.

    Raises:
        BankError: when the instruments the settings name cannot be read.
    """
    target = config.target
    bank = instrument_bank(config)
    parsed = parse_midi(path)
    midi = parsed if config.tempo is None else parsed.starting_at(config.tempo)
    grid = row_grid(midi, config)
    allocation = allocate(midi, grid, channels=config.channels)
    layout = Layout(height=config.pattern_rows, name=Path(path).stem)
    conversion = build_song(midi, allocation, grid, layout, target=target, bank=bank)
    return Converted(
        module=target.bind(conversion.song),
        midi=midi,
        grid=grid,
        bank=bank,
        conversion=conversion,
    )
