from __future__ import annotations

import pytest
from trackmod.trackers.xm.spec.effects import NIBBLE_PARAMETER, TEMPO_PARAMETER

from midi2tracker.timing.speed import MAX_SPEED, MIN_SPEED, select_speed
from midi2tracker.timing.tempo import tracker_tempo


def test_the_ceiling_is_what_a_note_delay_can_name() -> None:
    # A row divided into more ticks than a delay can address has positions no cell could express, which
    # is what used to make two different placements write the same effect.
    assert MAX_SPEED == NIBBLE_PARAMETER.maximum + 1


@pytest.mark.parametrize("beats_per_minute", [20.0, 60.0, 90.0, 120.0, 174.0, 240.0, 600.0])
@pytest.mark.parametrize("rows_per_beat", [1, 2, 4, 8, 15, 32])
def test_the_chosen_speed_keeps_the_fastest_tempo_inside_the_byte(beats_per_minute: float, rows_per_beat: int) -> None:
    speed = select_speed(beats_per_minute, rows_per_beat)
    assert MIN_SPEED <= speed <= MAX_SPEED
    tempo = tracker_tempo(beats_per_minute, speed=speed, rows_per_beat=rows_per_beat)
    assert tempo <= TEMPO_PARAMETER.maximum or speed == MIN_SPEED


@pytest.mark.parametrize("rows_per_beat", [1, 2, 4, 8, 15])
def test_the_chosen_speed_is_the_finest_one_that_fits(rows_per_beat: int) -> None:
    # Sub-row resolution is the only thing a higher speed buys, so leaving any on the table is a loss.
    speed = select_speed(120.0, rows_per_beat)
    if speed < MAX_SPEED:
        assert tracker_tempo(120.0, speed=speed + 1, rows_per_beat=rows_per_beat) > TEMPO_PARAMETER.maximum


def test_a_piece_too_fast_for_any_speed_still_converts() -> None:
    # The tempo is then clamped and the piece plays slower, which is a result rather than a refusal.
    speed = select_speed(600.0, rows_per_beat=32)
    assert speed == MIN_SPEED
