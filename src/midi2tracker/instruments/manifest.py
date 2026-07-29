from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.selector import EVERY_NOTE, Selector
from midi2tracker.instruments.velocity import MeasuredVelocity

MANIFEST_VERSION: Final = 2
FIRST_INSTRUMENT: Final = 0


class SourceSpec(BaseModel):
    """Where one layer's instrument is stored: an entry of the bank, and which instrument inside it to take."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    file: str
    instrument: int = Field(default=FIRST_INSTRUMENT, ge=0)


class LayerSpec(BaseModel):
    """One instrument of a bank: what it plays, which notes reach it, and how it reads their velocity.

    Each layer was measured against its own samples, so the velocity map belongs here rather than to the
    bank as a whole, and the table is stated inline. A producer derives what it stores from what it
    measured, which makes the two one calibrated unit: keeping them in one document is what keeps a layer
    playing the dynamics its own waveforms were written for. A layer stating no map is read on the even
    scale.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    source: SourceSpec
    select: Selector = EVERY_NOTE
    velocity_map: MeasuredVelocity | None = None


class BankManifest(BaseModel):
    """The document describing a bank, naming each instrument as an entry of the bank it belongs to.

    This is the contract between a producer of sampled instruments and a conversion that plays them:
    layers in the order they are to be tried, each naming its instrument, the notes it answers, and the
    map its velocities were measured with. Fields outside this model are ignored, so a manifest written
    by a later producer still loads and contributes what it shares.

    An entry is named against the bank rather than against a directory, so the same document describes a
    bank shipped as one archive and one spread over a directory.
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
    def parse(cls, data: bytes, *, origin: str) -> BankManifest:
        """Read a manifest from the bytes a store holds it as, with ``origin`` naming where they came from.

        Raises:
            BankError: when the bytes describe a bank of another shape.
        """
        try:
            return cls.model_validate_json(data)
        except ValidationError as unreadable:
            raise BankError(f"{origin} does not read as a bank manifest: {unreadable}") from unreadable
