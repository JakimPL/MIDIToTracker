from __future__ import annotations

import json
from pathlib import Path

import pytest
from trackmod.spec.levels import MAX_VOLUME

from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.velocity import (
    VELOCITY_COUNT,
    LinearVelocity,
    MeasuredVelocity,
)
from tests.conftest import velocity_map_file


def test_the_even_scale_spends_the_whole_volume_column() -> None:
    linear = LinearVelocity()
    assert linear.volume(0) == 0
    assert linear.volume(127) == MAX_VOLUME
    assert linear.volume(64) == round(64 * MAX_VOLUME / 127)


def test_a_measured_map_states_the_volume_it_was_measured_at(tmp_path: Path) -> None:
    volumes = [min(MAX_VOLUME, velocity // 2 + 1) for velocity in range(VELOCITY_COUNT)]
    measured = MeasuredVelocity.load(velocity_map_file(tmp_path / "velocity_map.json", volumes))
    assert measured.volume(0) == volumes[0]
    assert measured.volume(127) == volumes[127]


def test_the_measurement_the_map_carries_alongside_the_table_is_left_alone(tmp_path: Path) -> None:
    # The producer records its anchors in the same document, and a reader that refused them would tie
    # this project to one version of that producer's output.
    volumes = [1] * VELOCITY_COUNT
    assert MeasuredVelocity.load(velocity_map_file(tmp_path / "velocity_map.json", volumes)).volume(60) == 1


def test_a_table_of_another_shape_is_reported_as_a_setting_to_correct(tmp_path: Path) -> None:
    path = tmp_path / "velocity_map.json"
    path.write_text(json.dumps({"volumes": [1, 2, 3]}), encoding="utf-8")
    with pytest.raises(BankError):
        MeasuredVelocity.load(path)


def test_a_velocity_map_that_is_not_there_is_reported_as_a_setting_to_correct(tmp_path: Path) -> None:
    with pytest.raises(BankError):
        MeasuredVelocity.load(tmp_path / "absent.json")
