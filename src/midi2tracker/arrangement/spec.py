from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from midi2tracker.instruments.manifest import LayerSpec
from midi2tracker.instruments.naming import (
    a_velocity_map_reads_an_instrument,
    one_source_of_instruments,
)


class TrackSpec(BaseModel):
    """What one track of an arrangement plays through, and how wide it may spread.

    The instruments are named exactly the way the settings name them for a single piece: a ``bank``, an
    ``instrument_file`` with the ``velocity_map`` it was measured against, or the ``layers`` a bank is
    made of stated here. Naming none plays the reserved slot a tracker fills in by hand.

    ``layers`` is a bank written where it is used rather than shipped as one, which is what a track
    assembled from loose instrument files asks for; each entry names its file against the arrangement
    document. ``name`` is what such a bank calls itself, defaulting to the track's own name.

    ``channels`` is this track's own ceiling: it steals within that many channels rather than reaching
    for another track's. A track stating none is held to the count the settings state.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    bank: Path | None = None
    instrument_file: Path | None = None
    velocity_map: Path | None = None
    layers: tuple[LayerSpec, ...] | None = Field(default=None, min_length=1)
    name: str | None = None
    channels: int | None = Field(default=None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def _the_short_forms_are_the_same_track(cls, stated: object) -> object:
        """A track stating a path alone names the bank it plays through, and one stating nothing is empty.

        Both are the mapping written the short way, so a document reads as the piece rather than as the
        model, and one code path serves every form.
        """
        if stated is None:
            return {}

        if isinstance(stated, str):
            return {"bank": stated}

        return stated

    @model_validator(mode="after")
    def _names_one_source_of_instruments(self) -> TrackSpec:
        one_source_of_instruments(
            {
                "bank": self.bank is not None,
                "instrument_file": self.instrument_file is not None,
                "layers": self.layers is not None,
            }
        )
        a_velocity_map_reads_an_instrument(
            velocity_map=self.velocity_map is not None,
            instrument_file=self.instrument_file is not None,
        )
        return self

    @property
    def instruments(self) -> str:
        """What two tracks state alike when they play through one set of instrument slots.

        Everything naming the bank counts and nothing else does, so two tracks pointed at one bank share
        its slots however widely their own ceilings differ.
        """
        return self.model_dump_json(include={"bank", "instrument_file", "velocity_map", "layers", "name"})
