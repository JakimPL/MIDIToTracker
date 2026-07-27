from __future__ import annotations

import pytest

from midi2tracker.song.height import pattern_height
from midi2tracker.tracker.target import TrackerTarget


@pytest.mark.parametrize("rows", [0, 1, 64, 1000, 30720])
def test_a_height_that_already_fits_is_left_alone(rows: int, target: TrackerTarget) -> None:
    assert pattern_height(rows, preferred=120, target=target) == 120 or rows > target.max_patterns * 120


def test_a_piece_too_long_for_the_height_asked_for_gets_taller_patterns(target: TrackerTarget) -> None:
    # Cutting a long piece at a short height runs out of order positions long before it runs out of
    # music, so the height gives way rather than the conversion failing.
    rows = target.max_patterns * 120 + 1
    height = pattern_height(rows, preferred=120, target=target)
    assert height > 120
    assert -(-rows // height) <= target.max_patterns


def test_a_height_below_what_the_format_accepts_gives_way_to_the_floor(target: TrackerTarget) -> None:
    # Impulse Tracker's own tracker reads patterns of at least 32 rows, so a shorter one asked for is
    # raised to that floor rather than written and refused.
    assert pattern_height(1, preferred=1, target=target) == target.min_rows


@pytest.mark.parametrize("rows", [1, 500, 30_000, 65_536, 200_000])
@pytest.mark.parametrize("preferred", [1, 64, 120, 256])
def test_the_height_stays_between_the_format_floor_and_ceiling(
    rows: int,
    preferred: int,
    target: TrackerTarget,
) -> None:
    assert target.min_rows <= pattern_height(rows, preferred=preferred, target=target) <= target.max_rows


@pytest.mark.parametrize("rows", [1, 500, 30_000])
def test_every_piece_the_format_can_hold_fits_the_order_table(rows: int, target: TrackerTarget) -> None:
    height = pattern_height(rows, preferred=1, target=target)
    assert -(-rows // height) <= target.max_patterns


def test_the_longest_piece_the_format_holds_still_fits_the_order_table(target: TrackerTarget) -> None:
    rows = target.max_patterns * target.max_rows
    height = pattern_height(rows, preferred=1, target=target)
    assert -(-rows // height) <= target.max_patterns


def test_a_piece_past_both_ceilings_needs_more_patterns_than_the_table_names(target: TrackerTarget) -> None:
    # There is no height left to give, which is what the module's own bounds then report.
    rows = target.max_patterns * target.max_rows + 1
    assert pattern_height(rows, preferred=1, target=target) == target.max_rows
    assert -(-rows // target.max_rows) > target.max_patterns
