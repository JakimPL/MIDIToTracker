from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.selector import EVERY_NOTE, Selector

MANIFEST_VERSION: Final = 1
FIRST_INSTRUMENT: Final = 0


class SourceSpec(BaseModel):
    """Where one layer's instrument is stored: a file, and which of the instruments in it to take."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    file: Path
    instrument: int = Field(default=FIRST_INSTRUMENT, ge=0)


class LayerSpec(BaseModel):
    """One instrument of a bank: what it plays, which notes reach it, and how it reads their velocity.

    Each layer was measured against its own samples, so the velocity map belongs here rather than to the
    bank as a whole. A layer stating none is read on the even scale.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    source: SourceSpec
    select: Selector = EVERY_NOTE
    velocity_map: Path | None = None


class BankManifest(BaseModel):
    """The document describing a bank, with every path in it read against the directory it sits in.

    This is the contract between a producer of sampled instruments and a conversion that plays them:
    layers in the order they are to be tried, each naming its instrument, the notes it answers, and the
    map its velocities were measured with. Fields outside this model are ignored, so a manifest written
    by a later producer still loads and contributes what it shares.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int
    name: str
    layers: tuple[LayerSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _states_a_version_this_reads(self) -> BankManifest:
        if self.version != MANIFEST_VERSION:
            raise ValueError(f"manifest states version {self.version}, where version {MANIFEST_VERSION} is read here")

        return self

    @classmethod
    def load(cls, path: Path) -> BankManifest:
        """Read a manifest from disk.

        Raises:
            BankError: when the file is unreadable or describes a bank of another shape.
        """
        try:
            return cls.model_validate_json(path.read_bytes())
        except (OSError, ValidationError) as unreadable:
            raise BankError(f"{path} does not read as a bank manifest: {unreadable}") from unreadable
