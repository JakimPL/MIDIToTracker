"""Where one event sits on the row grid: which row, and how far into it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Placement(BaseModel):
    """A row and the tracker ticks into it that an event actually starts on.

    A delay of zero means the event starts with the row, which is the only case a cell needs no effect
    to express.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    row: int = Field(ge=0)
    delay: int = Field(ge=0)

    @property
    def delayed(self) -> bool:
        """Whether expressing this placement costs a note-delay effect."""
        return self.delay > 0
