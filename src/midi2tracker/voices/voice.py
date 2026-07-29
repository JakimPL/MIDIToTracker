from pydantic import BaseModel, ConfigDict, Field

from midi2tracker.midi.events import NoteEvent
from midi2tracker.timing.placement import Placement


class Voice(BaseModel):
    """A note bound to a channel: which track it came from, where it starts, and where it releases.

    ``track`` is the piece the note was read out of, which is what says whose bank answers it once the
    tracks share one instrument table.

    The release carries no sub-row placement, because a key-off occupies a cell of its own and the note
    delay a cell can hold belongs to the note that starts there.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    note: NoteEvent
    track: int = Field(ge=0)
    channel: int = Field(ge=0)
    start: Placement
    release_row: int = Field(ge=0)

    @property
    def releases_later(self) -> bool:
        """Whether the release falls on a row of its own rather than inside the row that starts it."""
        return self.release_row > self.start.row
