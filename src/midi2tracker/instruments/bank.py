from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trackmod.core.instruments.instrument import Instrument
from trackmod.core.instruments.transfer import combine
from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.core.notes.pitch import Note
from trackmod.core.samples.sample import Sample

from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.manifest import FIRST_INSTRUMENT, BankManifest, LayerSpec
from midi2tracker.instruments.placeholder import placeholder_unit, reserved_unit
from midi2tracker.instruments.selector import EVERY_NOTE, Selector
from midi2tracker.instruments.source import load_unit
from midi2tracker.instruments.velocity import (
    VELOCITY_MAP_NAME,
    LinearVelocity,
    MeasuredVelocity,
    VelocityVolume,
)


@dataclass(frozen=True)
class Voicing:
    """What one note plays through: the instrument slot it names, and the volume its cell states."""

    slot: int
    volume: int


@dataclass(frozen=True)
class Layer:
    """One instrument of a bank, the notes it answers, and how it reads their velocity."""

    unit: InstrumentUnit
    select: Selector
    velocity: VelocityVolume


def _velocity(path: Path | None) -> VelocityVolume:
    """How one layer reads velocity: the map measured for it, or the even scale."""
    return LinearVelocity() if path is None else MeasuredVelocity.load(path)


def _layer(spec: LayerSpec, root: Path) -> Layer:
    """One manifest entry resolved against the directory the manifest sits in."""
    return Layer(
        unit=load_unit(root / spec.source.file, spec.source.instrument),
        select=spec.select,
        velocity=_velocity(None if spec.velocity_map is None else root / spec.velocity_map),
    )


@dataclass(frozen=True)
class Bank:
    """The instruments a conversion plays through, and how a note finds one.

    Layers are tried in order and the first whose every stated band covers the note answers it, so a bank
    reads from its most particular case to its most general. ``offset`` is where the layers sit in the
    song's instrument table; the slots below them are numbered and hold nothing.
    """

    layers: tuple[Layer, ...]
    offset: int

    @classmethod
    def placeholder(cls, *, offset: int) -> Bank:
        """A bank of one empty slot, which is what a conversion naming no instrument plays through."""
        return cls(
            layers=(Layer(unit=placeholder_unit(), select=EVERY_NOTE, velocity=LinearVelocity()),),
            offset=offset,
        )

    @classmethod
    def from_instrument(cls, path: Path, *, velocity_map: Path | None, offset: int) -> Bank:
        """A bank of one instrument file, answering every note.

        A velocity map stated is read; otherwise one sitting beside the instrument is picked up, which is
        how a producer lays its output directory out.

        Raises:
            BankError: when the instrument or its velocity map cannot be read.
        """
        beside = path.parent / VELOCITY_MAP_NAME
        measured = velocity_map if velocity_map is not None else (beside if beside.is_file() else None)
        layer = Layer(
            unit=load_unit(path, FIRST_INSTRUMENT),
            select=EVERY_NOTE,
            velocity=_velocity(measured),
        )
        return cls(layers=(layer,), offset=offset)

    @classmethod
    def from_manifest(cls, path: Path, *, offset: int) -> Bank:
        """The bank a manifest describes, with its paths read against the directory it sits in.

        Raises:
            BankError: when the manifest, an instrument it names, or a velocity map cannot be read.
        """
        manifest = BankManifest.load(path)
        root = path.parent
        return cls(layers=tuple(_layer(spec, root) for spec in manifest.layers), offset=offset)

    @property
    def units(self) -> tuple[InstrumentUnit, ...]:
        """Every slot the song numbers: the reserved ones, and then one for each layer."""
        return (*(reserved_unit() for _ in range(self.offset)), *(layer.unit for layer in self.layers))

    @property
    def content(self) -> tuple[tuple[Instrument, ...], tuple[Sample, ...]]:
        """The instrument and sample tables a song takes, each keymap restated against the flat one."""
        return combine(self.units)

    def voicing(self, key: Note, expression: Expression) -> Voicing | None:
        """The slot and volume one note plays at, or nothing when the bank leaves it silent.

        A note reaches the first layer whose every stated band covers it, and sounds when that layer's
        keymap routes its key to a sample. A key the layer leaves unrouted is silence the run reports,
        since a sampled instrument covers the stretch of the keyboard it was recorded over.
        """
        for position, layer in enumerate(self.layers):
            if not layer.select.covers(expression):
                continue

            if layer.unit.instrument.assignment(key) is None:
                return None

            return Voicing(slot=self.offset + position, volume=layer.velocity.volume(expression.velocity))

        return None
