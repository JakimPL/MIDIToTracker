from __future__ import annotations

import pytest

from midi2tracker.midi.events import MidiSong, TempoEvent
from tests.conftest import PULSES, midi_song, note


def test_a_song_rescaled_to_its_own_resolution_is_the_song_it_was() -> None:
    song = midi_song(note(0, 48), note(96, 24))
    assert song.rescaled(PULSES) == song


def test_every_tick_lands_where_it_did_on_the_finer_scale() -> None:
    # A beat is a beat whichever resolution counts it, so doubling the pulses doubles every tick.
    song = midi_song(note(0, 48), note(96, 24))
    rescaled = song.rescaled(PULSES * 2)
    assert rescaled.pulses_per_beat == PULSES * 2
    assert [(event.tick_on, event.tick_off) for event in rescaled.notes] == [(0, 96), (192, 240)]


def test_the_tempo_map_moves_with_the_notes() -> None:
    tempos = (
        TempoEvent.at_beats_per_minute(0, 120.0),
        TempoEvent.at_beats_per_minute(192, 150.0),
    )
    rescaled = midi_song(note(0, 48), tempos=tempos).rescaled(PULSES * 5)
    assert [event.tick for event in rescaled.tempos] == [0, 960]
    assert [round(event.beats_per_minute) for event in rescaled.tempos] == [120, 150]


def test_a_note_keeps_the_share_of_a_beat_it_sounded_for() -> None:
    song = midi_song(note(0, PULSES // 4))
    rescaled = song.rescaled(PULSES * 3)
    assert rescaled.notes[0].ticks / rescaled.pulses_per_beat == song.notes[0].ticks / song.pulses_per_beat


def test_a_resolution_the_ticks_would_not_land_on_is_refused() -> None:
    # A factor that is not whole would put events between the beats their own file wrote them on.
    with pytest.raises(ValueError, match="no multiple"):
        midi_song(note(0, 48)).rescaled(PULSES + 1)


def test_two_files_meet_on_the_resolution_that_states_both_exactly() -> None:
    """480 and 384 pulses a beat are the two a producer of MIDI commonly writes, and 1920 states both.

    Combining tracks is what asks for one scale, and taking the least common multiple is what keeps each
    file's own beats where it put them.
    """
    quarter = MidiSong(
        pulses_per_beat=480,
        notes=(note(480, 480),),
        tempos=(TempoEvent.at_beats_per_minute(0, 120.0),),
    )
    third = MidiSong(
        pulses_per_beat=384,
        notes=(note(384, 384),),
        tempos=(TempoEvent.at_beats_per_minute(0, 120.0),),
    )
    common = 1920
    assert quarter.rescaled(common).notes[0].tick_on == common
    assert third.rescaled(common).notes[0].tick_on == common
