from __future__ import annotations

from midi2tracker.midi.sustain import SustainedVoices


def played(voices: SustainedVoices, *, tick: int, minimum: int = 0) -> list[tuple[int, int, int]]:
    return [(note.pitch, note.tick_on, note.tick_off) for note in voices.finish(tick=tick, minimum=minimum)]


def test_a_key_pressed_and_released_sounds_for_exactly_that_long() -> None:
    voices = SustainedVoices()
    voices.press(60, tick=0, velocity=100)
    voices.release(60, tick=48)
    assert played(voices, tick=48) == [(60, 0, 48)]


def test_a_key_released_under_the_pedal_keeps_sounding_until_the_pedal_lifts() -> None:
    # This is the whole reason the pedal is modelled: the release the file records is not the release
    # the music has.
    voices = SustainedVoices()
    voices.press(60, tick=0, velocity=100)
    voices.pedal(down=True, tick=10)
    voices.release(60, tick=20)
    assert voices.closed == []  # the key is up, but the voice is still sounding

    voices = SustainedVoices()
    voices.press(60, tick=0, velocity=100)
    voices.pedal(down=True, tick=10)
    voices.release(60, tick=20)
    voices.pedal(down=False, tick=96)
    assert played(voices, tick=96) == [(60, 0, 96)]


def test_pressing_a_pedal_held_key_again_ends_the_ringing_one_first() -> None:
    # One channel plays one voice, so the same key sounding twice at once is not something the module
    # could express — and not what a piano does either.
    voices = SustainedVoices()
    voices.press(60, tick=0, velocity=100)
    voices.pedal(down=True, tick=10)
    voices.release(60, tick=20)
    voices.press(60, tick=48, velocity=90)
    voices.release(60, tick=72)
    assert played(voices, tick=72) == [(60, 0, 48), (60, 48, 72)]


def test_lifting_the_pedal_ends_every_key_it_was_holding() -> None:
    voices = SustainedVoices()
    for pitch in (60, 64, 67):
        voices.press(pitch, tick=0, velocity=100)

    voices.pedal(down=True, tick=10)
    for pitch in (60, 64, 67):
        voices.release(pitch, tick=20)

    voices.pedal(down=False, tick=96)
    assert played(voices, tick=96) == [(60, 0, 96), (64, 0, 96), (67, 0, 96)]


def test_a_key_still_held_at_the_end_rings_to_where_the_music_stops() -> None:
    voices = SustainedVoices()
    voices.press(60, tick=0, velocity=100)
    assert played(voices, tick=192) == [(60, 0, 192)]


def test_a_key_held_past_the_last_event_still_sounds_for_a_beat() -> None:
    # A file that simply stops on a note-on would otherwise leave it no length at all.
    voices = SustainedVoices()
    voices.press(60, tick=100, velocity=100)
    assert played(voices, tick=100, minimum=96) == [(60, 100, 196)]


def test_a_release_for_a_key_that_is_not_down_is_passed_over() -> None:
    voices = SustainedVoices()
    voices.release(60, tick=10)
    assert played(voices, tick=10) == []


def test_the_pedal_lifting_with_nothing_held_leaves_the_state_clean() -> None:
    voices = SustainedVoices()
    voices.pedal(down=True, tick=0)
    voices.pedal(down=False, tick=10)
    voices.press(60, tick=20, velocity=100)
    voices.release(60, tick=40)
    assert played(voices, tick=40) == [(60, 20, 40)]
