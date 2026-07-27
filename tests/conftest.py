from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import mido
import numpy as np
import pytest
from trackmod.core.instruments.instrument import Instrument
from trackmod.core.instruments.keymap import KeyAssignment, routed_keymap
from trackmod.core.notes.pitch import Note
from trackmod.core.patterns.builder import PatternBuilder
from trackmod.core.samples.sample import Sample
from trackmod.core.songs.order import OrderList
from trackmod.core.songs.playback import Playback
from trackmod.core.songs.song import Song
from trackmod.limits.compliance import Compliance
from trackmod.spec.levels import MAX_VOLUME
from trackmod.trackers.it.module import ITModule

from midi2tracker.midi.events import MidiSong, NoteEvent, TempoEvent
from midi2tracker.spec import DEFAULT_MICROSECONDS_PER_BEAT, SUSTAIN_CONTROLLER
from midi2tracker.timing.grid import RowGrid
from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.tracker.target import TrackerTarget

DATA = Path(__file__).parent / "data"
PULSES = 96
SAMPLE_RATE = 44100
SAMPLE_FRAMES = 64
SAMPLED_KEYS = range(48, 73)


def canonical(tracker_format: TrackerFormat) -> TrackerTarget:
    """One format's target at the compliance a conversion writes under by default."""
    return TrackerTarget(format=tracker_format, compliance=Compliance.CANONICAL)


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


def sampled_instrument(name: str, keys: range) -> Instrument:
    """An instrument sounding one sample over ``keys``, each key at its own pitch and the rest silent.

    A real sampled instrument covers the stretch of the keyboard it was recorded over, so a narrow range
    is what a test needs to say something about the keys outside it.
    """
    keymap = routed_keymap(
        {Note.from_midi(pitch): KeyAssignment(sample=0, note=Note.from_midi(pitch)) for pitch in keys}
    )
    return Instrument(name=name, keymap=keymap)


def instrument_file(
    path: Path,
    *,
    keys: range = SAMPLED_KEYS,
    name: str = "Sampled",
    copies: int = 1,
    gain: int = MAX_VOLUME,
) -> Path:
    """A module holding sampled instruments, which is what a bank reads its layers out of."""
    sample = Sample(name=name, pcm=np.zeros(SAMPLE_FRAMES), rate=SAMPLE_RATE, volume=MAX_VOLUME, gain=gain)
    song = Song(
        name=name,
        channels=2,
        patterns=(PatternBuilder(rows=32, channels=2).build(),),
        order=OrderList.sequential(1),
        instruments=tuple(sampled_instrument(f"{name} {index}", keys) for index in range(copies)),
        samples=(sample,),
        playback=Playback(speed=6, tempo=125),
    )
    ITModule.from_song(song, compliance=Compliance.CANONICAL).save(path)
    return path


def velocity_map_file(path: Path, volumes: Sequence[int]) -> Path:
    """A velocity map as a producer writes it, carrying its measurement alongside the table."""
    document = {
        "reference_volume": max(volumes),
        "anchors": [{"velocity": 64, "loudness_lufs": -20.0, "volume": volumes[64]}],
        "volumes": list(volumes),
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


@pytest.fixture(params=tuple(TrackerFormat), ids=tuple(TrackerFormat))
def target(request: pytest.FixtureRequest) -> TrackerTarget:
    """Every format a module is written as, so a pass is checked through each of them."""
    return canonical(request.param)


@pytest.fixture
def grid() -> RowGrid:
    """Four rows a beat at six ticks a row, which divides a 96-pulse beat exactly."""
    return RowGrid(pulses_per_beat=PULSES, rows_per_beat=4, speed=6)


@pytest.fixture
def piece() -> Path:
    """A short real MIDI file, the one fixture the end-to-end tests convert."""
    return DATA / "test.mid"
