from pydantic import BaseModel, ConfigDict, Field

from midi2tracker.spec import MODULE_NAME


class Layout(BaseModel):
    """How a song is arranged: the pattern height asked for, and the module's name.

    ``height`` is a preference rather than a rule — a piece too long to be cut at that height is cut at a
    taller one instead, so the order table still names every pattern.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    height: int = Field(ge=1)
    name: str = MODULE_NAME
