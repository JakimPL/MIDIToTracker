from __future__ import annotations

from typing import Final

from pydantic import ConfigDict, RootModel

from midi2tracker.instruments.axis import Axis, Band
from midi2tracker.instruments.expression import Expression


class Selector(RootModel[dict[Axis, Band]]):
    """Which notes one layer of a bank answers: a band on each axis it states.

    An axis left out answers the whole of it, so a selector stating nothing answers every note. That is
    what keeps a bank of one instrument the same object as a layered one.
    """

    model_config = ConfigDict(frozen=True)

    root: dict[Axis, Band] = {}

    def covers(self, expression: Expression) -> bool:
        """Whether every band this selector states reaches the note."""
        return all(band.contains(expression.coordinate(axis)) for axis, band in self.root.items())


EVERY_NOTE: Final = Selector()
