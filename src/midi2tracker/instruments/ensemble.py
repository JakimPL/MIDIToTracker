from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from trackmod.core.instruments.transfer import combine
from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.core.notes.pitch import Note
from trackmod.core.voices.voices import InstrumentVoices

from midi2tracker.instruments.bank import Bank, Voicing
from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.placeholder import reserved_unit


@dataclass(frozen=True)
class Placement:
    """One bank in the song's instrument table: the bank, and the slot its first layer sits on."""

    bank: Bank
    offset: int


@dataclass(frozen=True)
class Ensemble:
    """Every bank a piece plays through, laid out as the one instrument table a song numbers.

    Each track names the bank its notes sound through, and tracks handed the same bank share its slots,
    so a bank two tracks play costs one set of instruments and stores its samples once. ``reserved`` is
    how many slots sit below the first bank, which is what starting a piece's instruments partway into
    the table amounts to: a tracker numbers them and nothing reaches them.
    """

    placements: tuple[Placement, ...]
    tracks: tuple[int, ...]
    reserved: int

    @classmethod
    def of(cls, banks: Sequence[Bank], *, reserved: int) -> Ensemble:
        """The table ``banks`` make, one entry per track, placed in the order the tracks state them.

        Tracks holding the same bank share one placement, so what the instruments cost a module follows
        from the distinct banks rather than from how many tracks play through them.
        """
        placements: list[Placement] = []
        tracks: list[int] = []
        offset = reserved
        for bank in banks:
            position = next((index for index, placed in enumerate(placements) if placed.bank is bank), None)
            if position is None:
                position = len(placements)
                placements.append(Placement(bank=bank, offset=offset))
                offset += len(bank.layers)

            tracks.append(position)

        return cls(placements=tuple(placements), tracks=tuple(tracks), reserved=reserved)

    @property
    def banks(self) -> tuple[Bank, ...]:
        """The distinct banks the piece plays through, in the order they were placed."""
        return tuple(placement.bank for placement in self.placements)

    @property
    def units(self) -> tuple[InstrumentUnit, ...]:
        """Every slot the song numbers: the reserved ones, then each bank's layers in placement order."""
        return (
            *(reserved_unit() for _ in range(self.reserved)),
            *(unit for placement in self.placements for unit in placement.bank.units),
        )

    @property
    def table(self) -> InstrumentVoices:
        """The instrument table a song takes, each keymap restated against the one sample table behind it."""
        return combine(self.units)

    def voicing(self, track: int, key: Note, expression: Expression) -> Voicing | None:
        """The slot and volume one note of ``track`` plays at, or nothing where its bank leaves it silent.

        The bank answers from its own first layer and the placement moves that answer onto the slot the
        song numbers it as, so where a bank sits stays the ensemble's business alone.
        """
        placement = self.placements[self.tracks[track]]
        voicing = placement.bank.voicing(key, expression)
        if voicing is None:
            return None

        return replace(voicing, slot=voicing.slot + placement.offset)
