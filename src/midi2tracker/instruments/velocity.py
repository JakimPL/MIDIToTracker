from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from trackmod.spec.levels import MAX_VOLUME

from midi2tracker.instruments.error import BankError
from midi2tracker.spec import MAX_VELOCITY

VELOCITY_COUNT: Final = MAX_VELOCITY + 1

Level = Annotated[int, Field(ge=0, le=MAX_VOLUME)]


class VelocityVolume(Protocol):
    """How a layer reads the force a note was struck with as the volume its cell states."""

    def volume(self, velocity: int) -> int:
        """The volume ``velocity`` sounds at, on the tracker's own 0..64 scale."""


@dataclass(frozen=True)
class LinearVelocity:
    """Velocity spread evenly over the volume column.

    This is what a layer reads with when nothing was measured for it. It matches the played dynamic where
    a waveform's own level already stands for the velocity it was recorded at.
    """

    def volume(self, velocity: int) -> int:
        """The volume ``velocity`` sounds at, on the tracker's own 0..64 scale."""
        return round(velocity * MAX_VOLUME / MAX_VELOCITY)


class MeasuredVelocity(BaseModel):
    """The volume each velocity sounds at, measured from the samples one layer holds.

    A producer renders every velocity, measures its loudness and states the column that reproduces it, so
    a layer reading this map plays the dynamic its instrument was sampled with. Fields outside the table
    are ignored, which is what lets the same document carry the anchors the measurement came from.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    volumes: tuple[Level, ...] = Field(min_length=VELOCITY_COUNT, max_length=VELOCITY_COUNT)

    @classmethod
    def load(cls, path: Path) -> MeasuredVelocity:
        """Read the velocity map written beside an instrument.

        Raises:
            BankError: when the file is unreadable or states a table of another shape.
        """
        try:
            return cls.model_validate_json(path.read_bytes())
        except (OSError, ValidationError) as unreadable:
            raise BankError(f"{path} does not read as a velocity map: {unreadable}") from unreadable

    def volume(self, velocity: int) -> int:
        """The volume ``velocity`` sounds at, on the tracker's own 0..64 scale."""
        return self.volumes[velocity]
