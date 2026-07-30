from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Final

import yaml
from pydantic import model_validator
from trackmod.limits.compliance import Compliance

from midi2tracker.instruments.naming import (
    a_velocity_map_reads_an_instrument,
    one_source_of_instruments,
)
from midi2tracker.settings import AUTOMATIC_SPEED, Settings
from midi2tracker.timing.speed import speed_bound
from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.tracker.target import TrackerTarget

CONFIG_NAME: Final = "config.yaml"

DEFAULT_FORMAT: Final = TrackerFormat.IT
DEFAULT_COMPLIANCE: Final = Compliance.CANONICAL


class Config(Settings):
    """One conversion's settings, held to what the chosen tracker format carries.

    The counts answer to the format rather than to a fixed table, because the two formats bound them
    differently — Impulse Tracker plays 64 channels of 200-row patterns where FastTracker 2 plays 32 of
    256 — so each one is graded once the format is known. This is the whole of what a conversion is told,
    which is what makes it the one place that grading happens: an arrangement and the command line each
    state a part of it, and :meth:`updated` reads those parts as one.

    What the notes play through is named once: a ``bank`` for several instruments, or an
    ``instrument_file`` for one, with ``instrument`` giving the slot they start on. Naming neither writes
    the reserved slot a tracker fills in by hand.

    Every file a conversion reads is one the settings name. An ``instrument_file`` sounds the dynamics it
    was measured with when a ``velocity_map`` states them and reads velocity evenly otherwise, so what a
    run plays follows from what it was told rather than from what happens to sit beside a file.
    """

    format: TrackerFormat = DEFAULT_FORMAT
    compliance: Compliance = DEFAULT_COMPLIANCE
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

    def updated(self, *stated: Mapping[str, object]) -> Config:
        """These settings with each layer written over them in turn, graded again as a whole.

        Rebuilding the model rather than copying it is what holds a stated value to the same bounds a
        file's value answers to, so a number the format cannot carry is refused wherever it came from.

        Raises:
            ValidationError: when what the layers add up to leaves the range a field states.
        """
        merged = self.model_dump()
        for layer in stated:
            merged |= dict(layer)

        return Config.model_validate(merged)


def load(path: Path | None = None) -> Config:
    """Read a configuration from ``path``, else the working directory's, else the field defaults.

    Keys the file states outside this model are ignored, so a configuration written for another version
    still loads and simply contributes what it shares.
    """
    for candidate in (path, Path.cwd() / CONFIG_NAME):
        if candidate is not None and candidate.exists():
            return Config.model_validate(yaml.safe_load(candidate.read_text(encoding="utf-8")) or {})

    return Config()
