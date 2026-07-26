"""What a parsed MIDI file leaves behind: the notes it plays and the tempos it plays them at.

Both are stated in absolute ticks rather than the deltas the file stores, because everything downstream
places events on a row grid and needs to know where each one falls in the piece rather than how far it is
from the last one.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from midi2xm.spec import MAX_PITCH, MAX_VELOCITY, MICROSECONDS_PER_MINUTE

FROZEN = ConfigDict(frozen=True, extra="forbid")


class NoteEvent(BaseModel):
    """One sounded note: when it starts, when it releases, which key, and how hard it was struck."""

    model_config = FROZEN

    tick_on: int = Field(ge=0)
    tick_off: int = Field(ge=0)
    pitch: int = Field(ge=0, le=MAX_PITCH)
    velocity: int = Field(ge=1, le=MAX_VELOCITY)

    @model_validator(mode="after")
    def _releases_after_it_starts(self) -> NoteEvent:
        if self.tick_off < self.tick_on:
            raise ValueError(f"note at tick {self.tick_on} releases at {self.tick_off}, before it starts")

        return self

    @property
    def ticks(self) -> int:
        """How long the note sounds for."""
        return self.tick_off - self.tick_on


class TempoEvent(BaseModel):
    """A tempo change: from this tick on, a quarter note lasts ``microseconds_per_beat``."""

    model_config = FROZEN

    tick: int = Field(ge=0)
    microseconds_per_beat: int = Field(gt=0)

    @property
    def beats_per_minute(self) -> float:
        """The same tempo as a musical beats-per-minute figure."""
        return MICROSECONDS_PER_MINUTE / self.microseconds_per_beat

    @classmethod
    def at_beats_per_minute(cls, tick: int, beats_per_minute: float) -> TempoEvent:
        """The tempo event a musical beats-per-minute figure names."""
        return cls(tick=tick, microseconds_per_beat=round(MICROSECONDS_PER_MINUTE / beats_per_minute))


class MidiSong(BaseModel):
    """A parsed MIDI file, reduced to what a tracker module is built from.

    ``pulses_per_beat`` is the file's own tick resolution, so a tick count only means a duration when it
    is read against it.
    """

    model_config = FROZEN

    pulses_per_beat: int = Field(gt=0)
    notes: tuple[NoteEvent, ...]
    tempos: tuple[TempoEvent, ...] = Field(min_length=1)

    @property
    def fastest(self) -> float:
        """The highest tempo the piece reaches, which is what the row clock has to keep up with."""
        return max(tempo.beats_per_minute for tempo in self.tempos)

    @property
    def last_tick(self) -> int:
        """The tick the last note releases on."""
        return max((note.tick_off for note in self.notes), default=0)

    def starting_at(self, beats_per_minute: float) -> MidiSong:
        """The same song with its opening tempo replaced, which is what a tempo override asks for."""
        head = TempoEvent.at_beats_per_minute(self.tempos[0].tick, beats_per_minute)
        return self.model_copy(update={"tempos": (head, *self.tempos[1:])})
