from __future__ import annotations

import json
import zipfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Final

import mido
import numpy as np
import pytest
from trackmod.core.instruments.instrument import Instrument
from trackmod.core.instruments.keymap import KeyAssignment, routed_keymap
from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.core.notes.pitch import Note
from trackmod.core.patterns.builder import PatternBuilder
from trackmod.core.samples.sample import Sample
from trackmod.core.songs.order import OrderList
from trackmod.core.songs.playback import Playback
from trackmod.core.songs.song import Song
from trackmod.core.voices.voices import InstrumentVoices
from trackmod.limits.compliance import Compliance
from trackmod.module.instrument import InstrumentFile
from trackmod.spec.levels import MAX_VOLUME
from trackmod.trackers.it.instrument_file import ITInstrumentFile
from trackmod.trackers.it.module import ITModule
from trackmod.trackers.it.spec.identity import INSTRUMENT_EXTENSION as ITI_EXTENSION
from trackmod.trackers.xm.instrument_file import XMInstrumentFile
from trackmod.trackers.xm.spec.identity import INSTRUMENT_EXTENSION as XI_EXTENSION

from midi2tracker.arrangement.track import Track
from midi2tracker.instruments.bank import Bank
from midi2tracker.instruments.manifest import MANIFEST_VERSION
from midi2tracker.instruments.store import MANIFEST_NAME
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
BANK_TEMPO = 125


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


def track(song: MidiSong, *, channels: int, name: str = "Track") -> Track:
    """One track of an arrangement, playing through the slot a tracker fills in by hand.

    The passes below the arrangement read tracks rather than files, so this is what a song built in
    memory becomes before it is allocated.
    """
    return Track(name=name, midi=song, bank=Bank.placeholder(), channels=channels)


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


def tempo(beats_per_minute: float, tick: int) -> tuple[mido.MetaMessage, int]:
    """A tempo change as a file states it, so a test writes the clock its tracks are read against."""
    return mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(beats_per_minute)), tick


def sampled_instrument(name: str, keys: range) -> Instrument:
    """An instrument sounding one sample over ``keys``, each key at its own pitch and the rest silent.

    A real sampled instrument covers the stretch of the keyboard it was recorded over, so a narrow range
    is what a test needs to say something about the keys outside it.
    """
    keymap = routed_keymap(
        {Note.from_midi(pitch): KeyAssignment(sample=0, note=Note.from_midi(pitch)) for pitch in keys}
    )
    return Instrument(name=name, keymap=keymap)


def instrument_name(name: str, index: int) -> str:
    """What one instrument of a built module is called: its bank's name and its position in the file.

    A bank named with the empty string builds instruments carrying no name, which is what a module
    written by a tool that leaves the field blank holds.
    """
    return f"{name} {index}" if name else name


def sampled_waveform(name: str, gain: int) -> Sample:
    """The one waveform a built instrument's keys reach, reserved at full volume."""
    return Sample(name=name, pcm=np.zeros(SAMPLE_FRAMES), rate=SAMPLE_RATE, volume=MAX_VOLUME, gain=gain)


def _impulse_tracker_instrument(unit: InstrumentUnit) -> InstrumentFile:
    return ITInstrumentFile.from_unit(unit, compliance=Compliance.CANONICAL)


def _fast_tracker_instrument(unit: InstrumentUnit) -> InstrumentFile:
    return XMInstrumentFile.from_unit(unit, compliance=Compliance.CANONICAL)


INSTRUMENT_WRITERS: Final[Mapping[str, Callable[[InstrumentUnit], InstrumentFile]]] = {
    ITI_EXTENSION: _impulse_tracker_instrument,
    XI_EXTENSION: _fast_tracker_instrument,
}


def standalone_instrument(path: Path, *, keys: range = SAMPLED_KEYS, name: str = "Sampled") -> Path:
    """One instrument stored on its own, in whichever format the path's suffix names.

    This is what a producer ships when the instrument rather than a module is the product, and a bank
    reads it the same way it reads an instrument out of a module.
    """
    unit = InstrumentUnit(instrument=sampled_instrument(name, keys), samples=(sampled_waveform(name, MAX_VOLUME),))
    INSTRUMENT_WRITERS[path.suffix](unit).save(path)
    return path


def instrument_file(
    path: Path,
    *,
    keys: range = SAMPLED_KEYS,
    name: str = "Sampled",
    copies: int = 1,
    gain: int = MAX_VOLUME,
) -> Path:
    """A module holding sampled instruments, which is what a bank reads its layers out of."""
    sample = sampled_waveform(name, gain)
    song = Song(
        name=name,
        channels=2,
        patterns=(PatternBuilder(rows=32, channels=2).build(),),
        order=OrderList.sequential(1),
        voices=InstrumentVoices(
            instruments=tuple(sampled_instrument(instrument_name(name, index), keys) for index in range(copies)),
            samples=(sample,),
        ),
        playback=Playback(speed=6, tempo=125),
    )
    ITModule.from_song(song, compliance=Compliance.CANONICAL).save(path)
    return path


def instrument_voices(song: Song) -> InstrumentVoices:
    """The instrument table a song holds, which is what every module this converter writes addresses."""
    voices = song.voices
    assert isinstance(voices, InstrumentVoices), f"{song.name!r} addresses samples, so it holds no instruments"
    return voices


def velocity_table(volumes: Sequence[int]) -> dict[str, object]:
    """A velocity map as a producer states it, carrying its measurement alongside the table."""
    return {
        "reference_volume": max(volumes),
        "anchors": [{"velocity": 64, "loudness_lufs": -20.0, "volume": volumes[64]}],
        "volumes": list(volumes),
    }


def velocity_map_file(path: Path, volumes: Sequence[int]) -> Path:
    """A velocity map on its own, which is what the one-instrument settings name."""
    path.write_text(json.dumps(velocity_table(volumes)), encoding="utf-8")
    return path


def bank_document(layers: Sequence[Mapping[str, object]], *, name: str = "Bank") -> dict[str, object]:
    """The manifest describing a bank, at the version this reads."""
    return {"version": MANIFEST_VERSION, "name": name, "tempo": BANK_TEMPO, "layers": list(layers)}


def bank_manifest(path: Path, layers: Sequence[Mapping[str, object]], *, name: str = "Bank") -> Path:
    """A bank spread over a directory: the manifest, with the instruments it names beside it."""
    path.write_text(json.dumps(bank_document(layers, name=name)), encoding="utf-8")
    return path


def bank_container(
    path: Path,
    layers: Sequence[Mapping[str, object]],
    entries: Mapping[str, Path],
    *,
    name: str = "Bank",
) -> Path:
    """A bank shipped as one archive, which is the form a producer hands one on in.

    This is the writer's side of the contract stated by hand: what a producer has to lay down for a
    conversion to read a bank out of a single file.
    """
    with zipfile.ZipFile(path, "w") as container:
        container.writestr(MANIFEST_NAME, json.dumps(bank_document(layers, name=name)))
        for entry, source in entries.items():
            container.write(source, entry)

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
