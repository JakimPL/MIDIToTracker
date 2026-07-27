from __future__ import annotations

from enum import StrEnum, unique

from pydantic import BaseModel, ConfigDict, model_validator


@unique
class Axis(StrEnum):
    """A dimension of how a note was played, along which a bank chooses between its instruments.

    Velocity is the one axis today. Another is a member here, a field on
    :class:`~midi2tracker.instruments.expression.Expression`, and an arm in its reader — the manifest
    keeps its shape, since a selector names axes by these very strings.
    """

    VELOCITY = "velocity"


class Band(BaseModel):
    """A stretch of one axis, with both ends counted as inside it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: int
    high: int

    @model_validator(mode="after")
    def _reads_upward(self) -> Band:
        if self.high < self.low:
            raise ValueError(f"band {self.low}..{self.high} ends below where it begins")

        return self

    def contains(self, value: int) -> bool:
        """Whether ``value`` falls inside this stretch."""
        return self.low <= value <= self.high
