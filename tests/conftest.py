from __future__ import annotations

from pathlib import Path

import mido
import pytest

from midi2xm.midi.events import MidiSong, NoteEvent, TempoEvent
from midi2xm.spec import DEFAULT_MICROSECONDS_PER_BEAT, SUSTAIN_CONTROLLER
from midi2xm.timing.grid import RowGrid

DATA = Path(__file__).parent / "data"
PULSES = 96


def note(tick_on: int, ticks: int, pitch: int = 60, velocity: int = 100) -> NoteEvent:
    """One note of a fixed length, so a test states only what it cares about."""
    return NoteEvent(tick_on=tick_on, tick_off=tick_on + ticks, pitch=pitch, velocity=velocity)


def midi_song(*notes: NoteEvent, tempos: tuple[TempoEvent, ...] | None = None) -> MidiSong:
    """A parsed song built directly, for the passes that run downstream of the file."""
    opening = TempoEvent(tick=0, microseconds_per_beat=DEFAULT_MICROSECONDS_PER_BEAT)
    return MidiSong(pulses_per_beat=PULSES, notes=notes, tempos=tempos or (opening,))


def write_midi(path: Path, messages: list[tuple[mido.BaseMessage, int]], *, pulses: int = PULSES) -> Path:
    """Write a one-track MIDI file from messages given in absolute ticks.

    The messages are ordered by tick before the deltas are taken, so a test states them in whatever order
    reads most clearly.
    """
    midi = mido.MidiFile(ticks_per_beat=pulses)
    track = mido.MidiTrack()
    previous = 0
    for message, tick in sorted(messages, key=lambda entry: entry[1]):
        track.append(message.copy(time=tick - previous))
        previous = tick

    midi.tracks.append(track)
    midi.save(str(path))
    return path


def press(pitch: int, tick: int, velocity: int = 100) -> tuple[mido.Message, int]:
    return mido.Message("note_on", note=pitch, velocity=velocity), tick


def lift(pitch: int, tick: int) -> tuple[mido.Message, int]:
    return mido.Message("note_off", note=pitch, velocity=0), tick


def pedal(value: int, tick: int) -> tuple[mido.Message, int]:
    return mido.Message("control_change", control=SUSTAIN_CONTROLLER, value=value), tick


@pytest.fixture
def grid() -> RowGrid:
    """Four rows a beat at six ticks a row, which divides a 96-pulse beat exactly."""
    return RowGrid(pulses_per_beat=PULSES, rows_per_beat=4, speed=6)


@pytest.fixture
def piece() -> Path:
    """A short real MIDI file, the one fixture the end-to-end tests convert."""
    return DATA / "test.mid"
