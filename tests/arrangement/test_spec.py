from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from midi2tracker.arrangement.spec import TrackSpec

LAYER: dict[str, object] = {"source": {"file": "soft.iti"}}


def test_a_track_naming_two_sources_of_instruments_is_refused() -> None:
    with pytest.raises(ValidationError, match="state one"):
        TrackSpec.model_validate({"bank": "Piano.bank", "instrument_file": "piano.iti"})


def test_a_track_naming_layers_beside_a_bank_is_refused() -> None:
    # Layers state a bank where it is used, so naming a shipped one too leaves it open which plays.
    with pytest.raises(ValidationError, match="state one"):
        TrackSpec.model_validate({"bank": "Piano.bank", "layers": [LAYER]})


def test_a_velocity_map_with_no_instrument_file_to_read_is_refused() -> None:
    with pytest.raises(ValidationError, match="which file"):
        TrackSpec.model_validate({"velocity_map": "measured.json"})


def test_a_velocity_map_belongs_to_the_instrument_file_beside_it() -> None:
    spec = TrackSpec.model_validate({"instrument_file": "piano.iti", "velocity_map": "measured.json"})
    assert spec.instrument_file == Path("piano.iti") and spec.velocity_map == Path("measured.json")


def test_a_track_stating_no_layer_at_all_is_refused() -> None:
    with pytest.raises(ValidationError):
        TrackSpec.model_validate({"layers": []})


def test_a_channel_ceiling_is_at_least_one() -> None:
    with pytest.raises(ValidationError):
        TrackSpec.model_validate({"channels": 0})


def test_two_tracks_naming_one_bank_state_the_same_instruments() -> None:
    """What decides shared slots is what names the bank, so a wider ceiling still shares the instruments."""
    narrow = TrackSpec.model_validate({"bank": "Piano.bank", "channels": 4})
    wide = TrackSpec.model_validate({"bank": "Piano.bank", "channels": 16})
    assert narrow.instruments == wide.instruments


def test_two_tracks_naming_different_banks_state_different_instruments() -> None:
    first = TrackSpec.model_validate({"bank": "Piano.bank"})
    second = TrackSpec.model_validate({"bank": "Brass.bank"})
    assert first.instruments != second.instruments


def test_a_bank_named_the_short_way_and_the_long_way_is_one_bank() -> None:
    assert (
        TrackSpec.model_validate("Piano.bank").instruments
        == TrackSpec.model_validate({"bank": "Piano.bank"}).instruments
    )
