from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.core.notes.pitch import Note

from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.manifest import FIRST_INSTRUMENT, LayerSpec
from midi2tracker.instruments.placeholder import placeholder_unit
from midi2tracker.instruments.selector import EVERY_NOTE, Selector
from midi2tracker.instruments.source import parse_units, read_units, select_unit
from midi2tracker.instruments.store import BankStore
from midi2tracker.instruments.velocity import LinearVelocity, MeasuredVelocity, VelocityVolume
from midi2tracker.spec import INSTRUMENT_NAME


@dataclass(frozen=True)
class Voicing:
    """What one note plays through: the layer it names, and the volume its cell states.

    ``slot`` is counted from the bank's own first layer; where those layers sit in a song's instrument
    table is the ensemble's to say.
    """

    slot: int
    volume: int


@dataclass(frozen=True)
class Layer:
    """One instrument of a bank, the notes it answers, and how it reads their velocity."""

    unit: InstrumentUnit
    select: Selector
    velocity: VelocityVolume


def _velocity(measured: MeasuredVelocity | None) -> VelocityVolume:
    """How one layer reads velocity: the map measured for it, or the even scale."""
    return LinearVelocity() if measured is None else measured


def _layer(spec: LayerSpec, store: BankStore) -> Layer:
    """One manifest entry, read out of the store the bank is held in."""
    name = spec.source.file
    units = parse_units(store.read(name), extension=PurePosixPath(name).suffix, origin=name)
    return Layer(
        unit=select_unit(units, spec.source.instrument, origin=name),
        select=spec.select,
        velocity=_velocity(spec.velocity_map),
    )


@dataclass(frozen=True)
class Bank:
    """The instruments a conversion plays through, and how a note finds one.

    Layers are tried in order and the first whose every stated band covers the note answers it, so a bank
    reads from its most particular case to its most general.

    ``name`` is what the bank calls itself, which a run prints so a summary says which instruments the
    piece was played through.
    """

    name: str
    layers: tuple[Layer, ...]

    @classmethod
    def placeholder(cls) -> Bank:
        """A bank of one empty slot, which is what a conversion naming no instrument plays through."""
        return cls(
            name=INSTRUMENT_NAME,
            layers=(Layer(unit=placeholder_unit(), select=EVERY_NOTE, velocity=LinearVelocity()),),
        )

    @classmethod
    def from_instrument(cls, path: Path, *, velocity_map: Path | None) -> Bank:
        """A bank of one instrument file, answering every note.

        The velocity map is the caller's to name: stating one plays the dynamics a producer measured, and
        naming none reads velocity on the even scale, which is what a waveform already carrying the level
        it was recorded at asks for. The bank goes by what the instrument calls itself, falling back to
        the file it came out of when the instrument carries no name of its own.

        Raises:
            BankError: when the instrument or its velocity map cannot be read.
        """
        measured = None if velocity_map is None else MeasuredVelocity.load(velocity_map)
        layer = Layer(
            unit=select_unit(read_units(path), FIRST_INSTRUMENT, origin=str(path)),
            select=EVERY_NOTE,
            velocity=_velocity(measured),
        )
        return cls(name=layer.unit.instrument.name or path.stem, layers=(layer,))

    @classmethod
    def from_store(cls, store: BankStore) -> Bank:
        """The bank a store holds, each layer read out of the entry its manifest names.

        Raises:
            BankError: when the manifest, or an instrument it names, cannot be read.
        """
        manifest = store.manifest()
        return cls(name=manifest.name, layers=tuple(_layer(spec, store) for spec in manifest.layers))

    @property
    def units(self) -> tuple[InstrumentUnit, ...]:
        """The instruments the bank holds, one per layer and in the order they are tried."""
        return tuple(layer.unit for layer in self.layers)

    def voicing(self, key: Note, expression: Expression) -> Voicing | None:
        """The layer and volume one note plays at, or nothing when the bank leaves it silent.

        A note reaches the first layer whose every stated band covers it, and sounds when that layer's
        keymap routes its key to a sample. A key the layer leaves unrouted is silence the run reports,
        since a sampled instrument covers the stretch of the keyboard it was recorded over.
        """
        for position, layer in enumerate(self.layers):
            if not layer.select.covers(expression):
                continue

            if layer.unit.instrument.assignment(key) is None:
                return None

            return Voicing(slot=position, volume=layer.velocity.volume(expression.velocity))

        return None
