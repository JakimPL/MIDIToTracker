from __future__ import annotations

from trackmod.spec.levels import MAX_VOLUME
from trackmod.spec.pitch import NOTE_COUNT

from midi2tracker.song.instrument import held_envelope, placeholder_instrument, placeholder_sample


def test_the_envelope_holds_at_full_volume_while_the_key_is_down() -> None:
    # A curve that ran straight through to its silent point would mute any real waveform pasted into
    # the slot, however long the pattern grid says the note lasts.
    envelope = held_envelope()
    assert envelope.sustain is not None
    assert envelope.points[envelope.sustain.begin].value == MAX_VOLUME


def test_the_envelope_falls_to_silence_once_the_key_is_released() -> None:
    envelope = held_envelope()
    assert envelope.points[-1].value == 0
    assert envelope.points[-1].tick > envelope.points[0].tick


def test_the_sample_slot_is_reserved_empty_for_a_waveform_to_be_dropped_in() -> None:
    sample = placeholder_sample()
    assert sample.frames == 0
    assert sample.volume == MAX_VOLUME


def test_every_key_of_the_instrument_plays_the_reserved_sample_at_its_own_pitch() -> None:
    instrument = placeholder_instrument()
    assert len(instrument.keymap) == NOTE_COUNT
    assert all(assignment is not None and assignment.sample == 0 for assignment in instrument.keymap)
    assert all(
        assignment is not None and assignment.note.value == key for key, assignment in enumerate(instrument.keymap)
    )


def test_the_instrument_carries_the_holding_envelope() -> None:
    assert placeholder_instrument().volume_envelope == held_envelope()
