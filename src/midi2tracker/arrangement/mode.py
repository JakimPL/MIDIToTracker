from enum import StrEnum, unique
from typing import Final


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


DEFAULT_ALLOCATION: Final = ChannelAllocation.SEPARATED
