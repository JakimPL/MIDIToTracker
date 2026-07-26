from __future__ import annotations

import pytest
from trackmod.xm.spec.effects import NIBBLE_PARAMETER

from midi2tracker.timing.grid import RowGrid


def test_a_beat_spans_the_rows_it_was_asked_to(grid: RowGrid) -> None:
    assert grid.place(0).row == 0
    assert grid.place(grid.pulses_per_beat).row == grid.rows_per_beat


def test_a_tick_on_a_row_boundary_carries_no_delay(grid: RowGrid) -> None:
    for row in range(8):
        tick = row * grid.pulses_per_beat // grid.rows_per_beat
        assert grid.place(tick) == grid.place(tick).model_copy(update={"delay": 0})
        assert not grid.place(tick).delayed


def test_a_tick_between_rows_is_carried_by_the_delay(grid: RowGrid) -> None:
    # Halfway into a row of six ticks is three ticks in, which is what the note delay names.
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    placed = grid.place(ticks_per_row // 2)
    assert placed.row == 0
    assert placed.delay == grid.speed // 2


def test_a_tick_that_rounds_up_to_a_whole_row_moves_to_that_row(grid: RowGrid) -> None:
    # Naming a delay of exactly one row would ask the row for time it does not have.
    ticks_per_row = grid.pulses_per_beat // grid.rows_per_beat
    placed = grid.place(ticks_per_row - 1)
    assert placed.row == 1
    assert placed.delay == 0


@pytest.mark.parametrize("speed", range(1, NIBBLE_PARAMETER.maximum + 2))
@pytest.mark.parametrize("pulses", [96, 192, 480, 960])
def test_every_delay_the_grid_produces_can_be_named_by_a_note_delay(pulses: int, speed: int) -> None:
    # The delay is a nibble, so a grid that produced a wider one would silently collide with another
    # delay when the effect was written.
    grid = RowGrid(pulses_per_beat=pulses, rows_per_beat=4, speed=speed)
    delays = {grid.place(tick).delay for tick in range(2 * pulses)}
    assert all(NIBBLE_PARAMETER.contains(delay) for delay in delays)


@pytest.mark.parametrize("pulses", [96, 192, 480, 960])
def test_placement_never_moves_an_event_backwards(pulses: int) -> None:
    grid = RowGrid(pulses_per_beat=pulses, rows_per_beat=4, speed=6)
    rows = [grid.place(tick).row for tick in range(0, 4 * pulses, 7)]
    assert rows == sorted(rows)


def test_row_of_agrees_with_the_full_placement(grid: RowGrid) -> None:
    for tick in range(0, 4 * grid.pulses_per_beat, 5):
        assert grid.row_of(tick) == grid.place(tick).row
