from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from trackmod.trackers.xm.spec.ranges import (
    CANONICAL_MAX_CHANNELS,
    CANONICAL_MAX_INSTRUMENTS,
    MAX_ROWS,
)

from midi2tracker.timing.speed import MAX_SPEED

CONFIG_NAME = "config.yaml"
AUTOMATIC_SPEED = 0

DEFAULT_ROWS_PER_BEAT = 4
DEFAULT_CHANNELS = CANONICAL_MAX_CHANNELS
DEFAULT_PATTERN_ROWS = MAX_ROWS
DEFAULT_INSTRUMENT = 1


class Config(BaseModel):
    """One conversion's settings, held to what a canonical FastTracker 2 module can carry."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    rows_per_beat: int = Field(default=DEFAULT_ROWS_PER_BEAT, ge=1, le=MAX_ROWS)
    channels: int = Field(default=DEFAULT_CHANNELS, ge=1, le=CANONICAL_MAX_CHANNELS)
    pattern_rows: int = Field(default=DEFAULT_PATTERN_ROWS, ge=1, le=MAX_ROWS)
    speed: int = Field(default=AUTOMATIC_SPEED, ge=AUTOMATIC_SPEED, le=MAX_SPEED)
    tempo: float | None = Field(default=None, gt=0)
    instrument: int = Field(default=DEFAULT_INSTRUMENT, ge=1, le=CANONICAL_MAX_INSTRUMENTS)

    @property
    def slot(self) -> int:
        """The instrument's index in the song, counted from zero as the model counts them."""
        return self.instrument - 1

    @property
    def automatic_speed(self) -> bool:
        """Whether the speed is chosen from the music rather than stated."""
        return self.speed == AUTOMATIC_SPEED


def load(path: Path | None = None) -> Config:
    """Read a configuration from ``path``, else the working directory's, else the field defaults.

    Keys the file states outside this model are ignored, so a configuration written for another version
    still loads and simply contributes what it shares.
    """
    for candidate in (path, Path.cwd() / CONFIG_NAME):
        if candidate is not None and candidate.exists():
            return Config.model_validate(yaml.safe_load(candidate.read_text(encoding="utf-8")) or {})

    return Config()
