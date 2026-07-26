"""One note, once it knows which tracker channel plays it and where on the grid it lands."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from midi2xm.midi.events import NoteEvent
from midi2xm.timing.placement import Placement


class Voice(BaseModel):
    """A note bound to a channel: where it starts, how far into that row, and where it releases.

    The release carries no sub-row placement, because a key-off occupies a cell of its own and the note
    delay a cell can hold belongs to the note that starts there.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    note: NoteEvent
    channel: int = Field(ge=0)
    start: Placement
    release_row: int = Field(ge=0)

    @property
    def releases_later(self) -> bool:
        """Whether the release falls on a row of its own rather than inside the row that starts it."""
        return self.release_row > self.start.row
