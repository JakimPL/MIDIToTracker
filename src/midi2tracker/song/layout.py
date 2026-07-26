"""The choices a caller makes about how a converted piece is laid out.

None of these change what the music is: they decide how it is arranged on the grid — how tall the patterns
are cut, which instrument slot the notes name, and what the module is called. They travel together because
they are decided together, at the boundary, from one configuration.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from midi2tracker.spec import MODULE_NAME


class Layout(BaseModel):
    """How a song is arranged: the pattern height asked for, the instrument slot, and the module's name.

    ``height`` is a preference rather than a rule — a piece too long to be cut at that height is cut at a
    taller one instead, so the order table still names every pattern.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    height: int = Field(ge=1)
    slot: int = Field(ge=0)
    name: str = MODULE_NAME
