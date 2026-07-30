from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from midi2tracker.spec import MAX_PITCH, MAX_VELOCITY, MICROSECONDS_PER_MINUTE

FROZEN = ConfigDict(frozen=True, extra="forbid")
ONE_TO_ONE: Final = 1  # the factor a rescaling to the resolution a song already counts in works out as
OPENING_TICK: Final = 0


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
        return cls(
            tick=tick,
            microseconds_per_beat=round(MICROSECONDS_PER_MINUTE / beats_per_minute),
        )


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

    def at_one_tempo(self, beats_per_minute: float) -> MidiSong:
        """The same music played at one tempo throughout, which is what a stated tempo asks for.

        The whole map gives way to that single tempo, so the piece keeps the beat it was told to keep
        wherever the file changed its mind.
        """
        stated = TempoEvent.at_beats_per_minute(OPENING_TICK, beats_per_minute)
        return self.model_copy(update={"tempos": (stated,)})

    def rescaled(self, pulses_per_beat: int) -> MidiSong:
        """The same music counted against a finer resolution, which is how several files share one scale.

        Every tick is multiplied by a whole factor, so each event lands on the beat it already landed on
        and the music is stated exactly as it was written.

        Raises:
            ValueError: when the resolution asked for is no whole multiple of this song's own.
        """
        if pulses_per_beat % self.pulses_per_beat:
            raise ValueError(
                f"{pulses_per_beat} pulses a beat is no multiple of the {self.pulses_per_beat} this song "
                "counts in, so its ticks would land between beats"
            )

        factor = pulses_per_beat // self.pulses_per_beat
        if factor == ONE_TO_ONE:
            return self

        return self.model_copy(
            update={
                "pulses_per_beat": pulses_per_beat,
                "notes": tuple(
                    note.model_copy(update={"tick_on": note.tick_on * factor, "tick_off": note.tick_off * factor})
                    for note in self.notes
                ),
                "tempos": tuple(tempo.model_copy(update={"tick": tempo.tick * factor}) for tempo in self.tempos),
            }
        )
