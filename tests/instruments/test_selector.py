from __future__ import annotations

import pytest
from pydantic import ValidationError

from midi2tracker.instruments.axis import Axis, Band
from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.selector import EVERY_NOTE, Selector
from tests.conftest import note

MIDDLE_C = 60


def struck(velocity: int, pitch: int = MIDDLE_C) -> Expression:
    """One note's coordinates, so a test states the axis it is about."""
    return Expression(velocity=velocity, pitch=pitch)


def test_a_band_counts_both_of_its_ends() -> None:
    band = Band(low=10, high=20)
    assert band.contains(10) and band.contains(20) and band.contains(15)
    assert not band.contains(9) and not band.contains(21)


def test_a_band_ending_below_where_it_begins_is_refused() -> None:
    with pytest.raises(ValidationError):
        Band(low=20, high=10)


def test_a_selector_stating_nothing_answers_every_note() -> None:
    # This is what makes a bank of one instrument the same object as a layered one.
    assert all(EVERY_NOTE.covers(struck(velocity)) for velocity in (1, 64, 127))


def test_a_selector_answers_the_notes_its_bands_reach() -> None:
    quiet = Selector({Axis.VELOCITY: Band(low=0, high=63)})
    assert quiet.covers(struck(63))
    assert not quiet.covers(struck(64))


def test_a_selector_answers_the_keys_its_pitch_band_reaches() -> None:
    lower = Selector({Axis.PITCH: Band(low=0, high=59)})
    assert lower.covers(struck(100, pitch=59))
    assert not lower.covers(struck(100, pitch=60))


def test_a_selector_stating_two_axes_reaches_the_notes_both_bands_cover() -> None:
    corner = Selector({Axis.VELOCITY: Band(low=0, high=63), Axis.PITCH: Band(low=60, high=127)})
    assert corner.covers(struck(30, pitch=72))
    assert not corner.covers(struck(30, pitch=48))
    assert not corner.covers(struck(90, pitch=72))


def test_a_selector_reads_its_axes_by_the_names_a_manifest_states() -> None:
    # The manifest names axes with these very strings, so parsing one is what the document contract is.
    parsed = Selector.model_validate({"velocity": {"low": 100, "high": 127}, "pitch": {"low": 48, "high": 72}})
    assert parsed.covers(struck(120, pitch=48))
    assert not parsed.covers(struck(99, pitch=48))
    assert not parsed.covers(struck(120, pitch=47))


def test_a_note_reads_as_the_expression_it_was_played_with() -> None:
    expression = Expression.of(note(0, 48, pitch=60, velocity=88))
    assert expression.velocity == 88
    assert expression.pitch == 60
    assert expression.coordinate(Axis.VELOCITY) == 88
    assert expression.coordinate(Axis.PITCH) == 60
