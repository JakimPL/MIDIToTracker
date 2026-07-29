from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from trackmod.limits.compliance import Compliance

from midi2tracker.arrangement.mode import DEFAULT_ALLOCATION, ChannelAllocation
from midi2tracker.instruments.naming import (
    a_velocity_map_reads_an_instrument,
    one_source_of_instruments,
)
from midi2tracker.timing.speed import speed_bound
from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.tracker.target import TrackerTarget

CONFIG_NAME: Final = "config.yaml"
AUTOMATIC_SPEED: Final = 0

DEFAULT_FORMAT: Final = TrackerFormat.IT
DEFAULT_COMPLIANCE: Final = Compliance.CANONICAL
DEFAULT_ROWS_PER_BEAT: Final = 4
DEFAULT_CHANNELS: Final = 32
DEFAULT_PATTERN_ROWS: Final = 64
DEFAULT_INSTRUMENT: Final = 1


class Config(BaseModel):
    """One conversion's settings, held to what the chosen tracker format carries.

    The counts answer to the format rather than to a fixed table, because the two formats bound them
    differently — Impulse Tracker plays 64 channels of 200-row patterns where FastTracker 2 plays 32 of
    256 — so each one is graded once the format is known.

    What the notes play through is named once: a ``bank`` for several instruments, or an
    ``instrument_file`` for one, with ``instrument`` giving the slot they start on. Naming neither writes
    the reserved slot a tracker fills in by hand.

    ``channels`` is the ceiling one track allocates within, which an arrangement states per track and
    this states for the rest, and ``allocation`` is how the tracks of a piece share the channel table.

    Every file a conversion reads is one the settings name. An ``instrument_file`` sounds the dynamics it
    was measured with when a ``velocity_map`` states them and reads velocity evenly otherwise, so what a
    run plays follows from what it was told rather than from what happens to sit beside a file.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    format: TrackerFormat = DEFAULT_FORMAT
    compliance: Compliance = DEFAULT_COMPLIANCE
    rows_per_beat: int = Field(default=DEFAULT_ROWS_PER_BEAT, ge=1)
    channels: int = Field(default=DEFAULT_CHANNELS, ge=1)
    allocation: ChannelAllocation = DEFAULT_ALLOCATION
    pattern_rows: int = Field(default=DEFAULT_PATTERN_ROWS, ge=1)
    speed: int = Field(default=AUTOMATIC_SPEED, ge=AUTOMATIC_SPEED)
    tempo: float | None = Field(default=None, gt=0)
    instrument: int = Field(default=DEFAULT_INSTRUMENT, ge=1)
    bank: Path | None = None
    instrument_file: Path | None = None
    velocity_map: Path | None = None

    @model_validator(mode="after")
    def _names_one_source_of_instruments(self) -> Config:
        one_source_of_instruments({"bank": self.bank is not None, "instrument_file": self.instrument_file is not None})
        a_velocity_map_reads_an_instrument(
            velocity_map=self.velocity_map is not None,
            instrument_file=self.instrument_file is not None,
        )
        return self

    @model_validator(mode="after")
    def _within_the_format(self) -> Config:
        target = self.target
        ceilings = {
            "rows_per_beat": (self.rows_per_beat, target.max_rows),
            "channels": (self.channels, target.max_channels),
            "pattern_rows": (self.pattern_rows, target.max_rows),
            "speed": (self.speed, speed_bound(target).maximum),
            "instrument": (self.instrument, target.max_instruments),
        }
        for setting, (value, ceiling) in ceilings.items():
            if value > ceiling:
                raise ValueError(f"{setting} {value} is above {ceiling}, the most {self.format.upper()} carries")

        return self

    @property
    def target(self) -> TrackerTarget:
        """The format this conversion is written as, and the bounds it is held to."""
        return TrackerTarget(format=self.format, compliance=self.compliance)

    @property
    def slot(self) -> int:
        """Where the bank's instruments start in the song, counted from zero as the model counts them."""
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
