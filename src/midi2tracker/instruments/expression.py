from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from midi2tracker.instruments.axis import Axis
from midi2tracker.midi.events import NoteEvent
from midi2tracker.spec import MAX_VELOCITY


class Expression(BaseModel):
    """Where one note falls on the axes a bank routes along.

    A bank chooses an instrument from how a note was played, and the instrument's own keymap decides
    which sample the key then reaches — so the pitch stays out of this and the playing is all it carries.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    velocity: int = Field(ge=0, le=MAX_VELOCITY)

    @classmethod
    def of(cls, note: NoteEvent) -> Expression:
        """How a MIDI note was played, in the terms a bank reads."""
        return cls(velocity=note.velocity)

    def coordinate(self, axis: Axis) -> int:
        """Where this note falls along one axis."""
        match axis:
            case Axis.VELOCITY:
                return self.velocity
