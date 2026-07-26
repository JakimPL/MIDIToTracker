from __future__ import annotations

import pytest
from trackmod.xm.spec.ranges import MAX_PATTERNS, MAX_ROWS

from midi2xm.song.height import pattern_height


@pytest.mark.parametrize("rows", [0, 1, 64, 1000, 30720])
def test_a_height_that_already_fits_is_left_alone(rows: int) -> None:
    assert pattern_height(rows, preferred=120) == 120 or rows > MAX_PATTERNS * 120


def test_a_piece_too_long_for_the_height_asked_for_gets_taller_patterns() -> None:
    # Cutting a long piece at a short height runs out of order positions long before it runs out of
    # music, so the height gives way rather than the conversion failing.
    rows = MAX_PATTERNS * 120 + 1
    height = pattern_height(rows, preferred=120)
    assert height > 120
    assert -(-rows // height) <= MAX_PATTERNS


@pytest.mark.parametrize("rows", [1, 500, 30_000, 65_536, 200_000])
@pytest.mark.parametrize("preferred", [1, 64, 120, MAX_ROWS])
def test_the_height_never_leaves_the_row_ceiling(rows: int, preferred: int) -> None:
    assert 1 <= pattern_height(rows, preferred=preferred) <= MAX_ROWS


@pytest.mark.parametrize("rows", [1, 500, 30_000, MAX_PATTERNS * MAX_ROWS])
def test_every_piece_the_format_can_hold_fits_the_order_table(rows: int) -> None:
    height = pattern_height(rows, preferred=1)
    assert -(-rows // height) <= MAX_PATTERNS


def test_a_piece_past_both_ceilings_needs_more_patterns_than_the_table_names() -> None:
    # There is no height left to give, which is what the module's own bounds then report.
    rows = MAX_PATTERNS * MAX_ROWS + 1
    assert pattern_height(rows, preferred=1) == MAX_ROWS
    assert -(-rows // MAX_ROWS) > MAX_PATTERNS
