from pydantic import BaseModel, ConfigDict, Field

from midi2tracker.timing.placement import Placement


class RowGrid(BaseModel):
    """The mapping from MIDI ticks to rows, fixed by a file's resolution and the chosen row rate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pulses_per_beat: int = Field(gt=0)
    rows_per_beat: int = Field(ge=1)
    speed: int = Field(ge=1)

    def place(self, tick: int) -> Placement:
        """Where a tick falls: its row, and how many tracker ticks into that row it starts.

        The remainder is rounded to the nearest tracker tick, and a remainder that rounds up to a whole
        row moves to the next row rather than naming a delay the row has no time for.
        """
        row, remainder = divmod(tick * self.rows_per_beat, self.pulses_per_beat)
        delay = (remainder * self.speed + self.pulses_per_beat // 2) // self.pulses_per_beat
        if delay >= self.speed:
            return Placement(row=row + 1, delay=0)

        return Placement(row=row, delay=delay)

    def row_of(self, tick: int) -> int:
        """The row a tick lands on, for callers that have no use for the sub-row position."""
        return self.place(tick).row
