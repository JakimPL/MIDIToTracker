"""Reading a MIDI file down to the notes and tempos a tracker module is built from.

Every track is merged into one stream of absolute ticks, because a tracker has no notion of tracks — it
has channels, and which channel a note lands on is decided later by how many voices are sounding at once.
Sorting the merged stream by tick is what makes the pedal state machine correct: it sees the events in the
order a player would have produced them.
"""

from __future__ import annotations

from pathlib import Path

import mido

from midi2tracker.midi.events import MidiSong, NoteEvent, TempoEvent
from midi2tracker.midi.sustain import SustainedVoices
from midi2tracker.spec import DEFAULT_MICROSECONDS_PER_BEAT, PEDAL_DOWN, SUSTAIN_CONTROLLER


def _merged(midi: mido.MidiFile) -> list[tuple[int, mido.Message]]:
    """Every track's messages in one stream, timed in absolute ticks and ordered by when they happen."""
    events: list[tuple[int, mido.Message]] = []
    for track in midi.tracks:
        tick = 0
        for message in track:
            tick += message.time
            events.append((tick, message))

    events.sort(key=lambda event: event[0])
    return events


def _is_release(message: mido.Message) -> bool:
    """Whether a message lets a key go, which MIDI spells two ways."""
    return str(message.type) == "note_off" or (str(message.type) == "note_on" and message.velocity == 0)


SOUNDING = frozenset({"note_on", "note_off", "control_change"})


def _last_played(events: list[tuple[int, mido.Message]], *, default: int) -> int:
    """The tick the music stops on: the last event a player would have acted on.

    Meta events are passed over because a file may mark its end long after the last note, and a voice
    still sounding then should ring to where the music stops rather than through the padding.
    """
    return max((tick for tick, message in events if str(message.type) in SOUNDING), default=default)


def _tempos(events: list[tuple[int, mido.Message]]) -> tuple[TempoEvent, ...]:
    """Every tempo the file states, opening at the MIDI default so a piece always has one.

    Where several land on the same tick the last one wins, which is what a player reading the merged
    stream in order would end up playing.
    """
    stated = {0: TempoEvent(tick=0, microseconds_per_beat=DEFAULT_MICROSECONDS_PER_BEAT)}
    for tick, message in events:
        if message.type == "set_tempo":
            stated[tick] = TempoEvent(tick=tick, microseconds_per_beat=message.tempo)

    return tuple(stated[tick] for tick in sorted(stated))


def parse_midi(path: Path | str) -> MidiSong:
    """Read ``path`` into the notes and tempos it plays, with the sustain pedal already resolved."""
    midi = mido.MidiFile(str(path))
    events = _merged(midi)

    voices = SustainedVoices()
    for tick, message in events:
        if message.type == "note_on" and message.velocity > 0:
            voices.press(message.note, tick, message.velocity)
        elif _is_release(message):
            voices.release(message.note, tick)
        elif message.type == "control_change" and message.control == SUSTAIN_CONTROLLER:
            voices.pedal(down=message.value >= PEDAL_DOWN, tick=tick)

    end = _last_played(events, default=midi.ticks_per_beat)
    notes: list[NoteEvent] = voices.finish(tick=end, minimum=midi.ticks_per_beat)
    return MidiSong(pulses_per_beat=midi.ticks_per_beat, notes=tuple(notes), tempos=_tempos(events))
