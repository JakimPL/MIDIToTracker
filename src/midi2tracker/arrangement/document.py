from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from midi2tracker.arrangement.error import ArrangementError
from midi2tracker.arrangement.spec import TrackSpec
from midi2tracker.settings import Settings

ARRANGEMENT_EXTENSIONS: Final = frozenset({".yaml", ".yml"})
FIRST_TRACK: Final = 0


def arranges(extension: str) -> bool:
    """Whether a file with that extension is read as an arrangement rather than as one MIDI file."""
    return extension.lower() in ARRANGEMENT_EXTENSIONS


class ArrangementDocument(BaseModel):
    """Several MIDI files as one piece: what each plays through, and how they share the module.

    ``tracks`` maps each MIDI file onto the track it becomes, in the order the module lays them out. Every
    path the document states is read against the directory the document itself sits in, so an arrangement
    moves as one directory.

    ``clock`` names the track whose tempo map the whole piece follows, since a module states one clock;
    omitting it follows the first track. ``name`` falls back to the document's own file name.

    ``settings`` is how the piece is laid out — its grid, its tempo, its channels — stated with the piece
    so an arrangement written for a particular shape travels as one file. Each knob it leaves out falls to
    the configuration file, and a flag typed on the command line stands over both.

    Fields outside this shape are ignored, so a document written for a later version still loads and
    contributes what it shares.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str | None = None
    clock: Path | None = None
    settings: Settings = Field(default_factory=Settings)
    tracks: dict[Path, TrackSpec] = Field(min_length=1)

    @field_validator("settings", mode="before")
    @classmethod
    def _a_bare_block_states_nothing(cls, stated: object) -> object:
        """A ``settings:`` heading written with nothing under it leaves every knob to the layer beneath."""
        return {} if stated is None else stated

    @model_validator(mode="after")
    def _the_clock_is_one_of_the_tracks(self) -> ArrangementDocument:
        if self.clock is not None and self.clock not in self.tracks:
            stated = ", ".join(str(track) for track in self.tracks)
            raise ValueError(f"clock names {self.clock}, which is no track of this arrangement; {stated} are")

        return self

    @property
    def timekeeper(self) -> int:
        """Which track the piece follows the tempo of, counted in the order the document states them."""
        if self.clock is None:
            return FIRST_TRACK

        return list(self.tracks).index(self.clock)

    @classmethod
    def load(cls, path: Path) -> ArrangementDocument:
        """Read an arrangement document from disk.

        Raises:
            ArrangementError: when the file is unreadable or describes an arrangement of another shape.
        """
        try:
            stated = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as unreadable:
            raise ArrangementError(f"{path} does not read as an arrangement: {unreadable}") from unreadable

        try:
            document = cls.model_validate(stated or {})
        except ValidationError as invalid:
            raise ArrangementError(f"{path} does not read as an arrangement: {invalid}") from invalid

        return document if document.name is not None else document.model_copy(update={"name": path.stem})

    @classmethod
    def of(
        cls, midi: Path, *, bank: Path | None, instrument_file: Path | None, velocity_map: Path | None
    ) -> ArrangementDocument:
        """The arrangement one MIDI file and the settings naming its instruments amount to.

        Converting one file is the single-track case of the same document, so it is written as one and
        everything downstream sees the arrangement it always sees.
        """
        return cls(
            name=midi.stem,
            tracks={midi: TrackSpec(bank=bank, instrument_file=instrument_file, velocity_map=velocity_map)},
        )
