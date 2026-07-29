from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from midi2tracker.instruments.axis import Axis
from midi2tracker.midi.events import NoteEvent
from midi2tracker.spec import MAX_PITCH, MAX_VELOCITY


class Expression(BaseModel):
    """Where one note falls on the axes a bank routes along.

    The velocity picks the layer a producer measured that dynamic against, and the pitch picks between
    the instruments it wrote that layer's keyboard across, which a keymap alone tells apart only where
    each of those instruments answers its own keys. The chosen instrument's keymap then reaches the
    sample the key sounds.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    velocity: int = Field(ge=0, le=MAX_VELOCITY)
    pitch: int = Field(ge=0, le=MAX_PITCH)

    @classmethod
    def of(cls, note: NoteEvent) -> Expression:
        """Where a MIDI note falls on the axes a bank reads."""
        return cls(velocity=note.velocity, pitch=note.pitch)

    def coordinate(self, axis: Axis) -> int:
        """Where this note falls along one axis."""
        match axis:
            case Axis.VELOCITY:
                return self.velocity
            case Axis.PITCH:
                return self.pitch
