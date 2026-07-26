from __future__ import annotations

import pytest
from trackmod.xm.spec.effects import TEMPO_PARAMETER

from midi2xm.spec import TICKS_PER_BEAT
from midi2xm.timing.tempo import playable_tempo, tracker_tempo


def test_the_reference_clock_is_the_identity() -> None:
    # Six ticks a row over four rows a beat is the clock the tracker tempo was defined against, so a
    # musical tempo and a tracker tempo are the same number there.
    assert tracker_tempo(125.0, speed=6, rows_per_beat=4) == 125


def test_speed_and_rows_per_beat_both_scale_the_tempo() -> None:
    # A row keeps its duration when the speed and the tempo move together, which is what lets a higher
    # speed buy resolution without changing the music.
    base = tracker_tempo(120.0, speed=3, rows_per_beat=4)
    assert tracker_tempo(120.0, speed=6, rows_per_beat=4) == 2 * base
    assert tracker_tempo(120.0, speed=3, rows_per_beat=8) == 2 * base


def test_the_conversion_follows_the_definition() -> None:
    assert tracker_tempo(97.0, speed=5, rows_per_beat=7) == round(5 * 97.0 * 7 / TICKS_PER_BEAT)


@pytest.mark.parametrize(
    ("beats_per_minute", "speed", "rows_per_beat"),
    [(20.0, 1, 1), (600.0, 16, 32), (120.0, 6, 4), (40.0, 2, 3)],
)
def test_a_playable_tempo_always_lands_inside_the_parameter_byte(
    beats_per_minute: float, speed: int, rows_per_beat: int
) -> None:
    # The opening tempo is held to what the effect can name too, so a piece whose tempo changes can
    # still return to the one it started on.
    assert TEMPO_PARAMETER.contains(playable_tempo(beats_per_minute, speed=speed, rows_per_beat=rows_per_beat))


def test_a_tempo_inside_the_range_is_left_alone() -> None:
    assert playable_tempo(120.0, speed=6, rows_per_beat=4) == tracker_tempo(120.0, speed=6, rows_per_beat=4)
