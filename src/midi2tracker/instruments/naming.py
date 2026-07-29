from __future__ import annotations

from collections.abc import Mapping


def one_source_of_instruments(stated: Mapping[str, bool]) -> None:
    """Hold a setting to naming at most one source of the instruments its notes play through.

    Each source describes the whole bank, so naming two leaves it open which of them the piece plays.
    Naming none plays the reserved slot a tracker fills in by hand.

    Raises:
        ValueError: when several sources are named at once.
    """
    named = sorted(field for field, given in stated.items() if given)
    if len(named) > 1:
        listed = " and ".join(named)
        raise ValueError(f"{listed} each name what the notes play through, so state one")


def a_velocity_map_reads_an_instrument(*, velocity_map: bool, instrument_file: bool) -> None:
    """Hold a stated velocity map to naming the instrument file it was measured against.

    A map states the volume each velocity of one instrument sounds at, so which instrument it belongs to
    is part of what it means. A bank carries its own maps inside it.

    Raises:
        ValueError: when a map is named with no instrument file to read it with.
    """
    if velocity_map and not instrument_file:
        raise ValueError("velocity_map reads an instrument_file, so state which file it belongs to")
