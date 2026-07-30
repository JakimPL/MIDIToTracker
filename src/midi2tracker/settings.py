from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum, unique
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, ConfigDict, Field


@unique
class ChannelAllocation(StrEnum):
    """How the tracks of an arrangement share the channels the module states.

    ``SEPARATED`` gives each track a run of channels of its own, so a track's polyphony is answered by
    its own channels alone and the module reads as the stems it was assembled from. ``PACKED`` draws
    every track from one pool, so the tracks fill the gaps in each other's polyphony and the piece spans
    fewer channels.
    """

    PACKED = "packed"
    SEPARATED = "separated"


AUTOMATIC_SPEED: Final = 0

DEFAULT_ROWS_PER_BEAT: Final = 4
DEFAULT_CHANNELS: Final = 32
DEFAULT_PATTERN_ROWS: Final = 64
DEFAULT_INSTRUMENT: Final = 1
DEFAULT_ALLOCATION: Final = ChannelAllocation.SEPARATED

NO_OVERRIDES: Final[Mapping[str, object]] = MappingProxyType({})
STATED_PREFIX: Final = "Value error, "  # pydantic prepends this to the message a validator raises


class Settings(BaseModel):
    """How a piece is laid out, as far as one place states it.

    A conversion reads these from three places at once — the configuration file, the arrangement
    document, and the command line — so each of them states as much or as little as it has an opinion
    about and the layer beneath supplies the rest. :attr:`stated` is what carries that: it holds the
    knobs written down here and nothing else, which is what keeps an omitted ``tempo`` and a ``tempo``
    written as ``null`` two different answers.

    ``channels`` is the ceiling one track allocates within, which an arrangement states per track and
    this states for the rest, and ``allocation`` is how the tracks of a piece share the channel table.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    rows_per_beat: int = Field(default=DEFAULT_ROWS_PER_BEAT, ge=1)
    channels: int = Field(default=DEFAULT_CHANNELS, ge=1)
    allocation: ChannelAllocation = DEFAULT_ALLOCATION
    pattern_rows: int = Field(default=DEFAULT_PATTERN_ROWS, ge=1)
    speed: int = Field(default=AUTOMATIC_SPEED, ge=AUTOMATIC_SPEED)
    tempo: float | None = Field(default=None, gt=0)
    instrument: int = Field(default=DEFAULT_INSTRUMENT, ge=1)

    @property
    def stated(self) -> dict[str, object]:
        """Only the knobs written down here, so what is left out falls to the layer beneath."""
        return self.model_dump(exclude_unset=True)
