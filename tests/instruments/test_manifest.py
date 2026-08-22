from __future__ import annotations

import json
from typing import Final

import pytest

from midi2tracker.instruments.axis import Axis
from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.manifest import MANIFEST_VERSION, BankManifest
from midi2tracker.instruments.velocity import VELOCITY_COUNT
from tests.conftest import BANK_TEMPO, velocity_table

ORIGIN: Final = "bank.json"


def parsed(document: dict[str, object]) -> BankManifest:
    return BankManifest.parse(json.dumps(document).encode("utf-8"), origin=ORIGIN)


def test_the_document_a_producer_writes_reads_back_whole() -> None:
    manifest = parsed(
        {
            "version": MANIFEST_VERSION,
            "name": "Piano",
            "tempo": BANK_TEMPO,
            "layers": [
                {
                    "source": {"file": "instruments/module.it", "instrument": 0},
                    "select": {"velocity": {"low": 0, "high": 127}, "pitch": {"low": 29, "high": 101}},
                    "velocity_map": velocity_table([17] * VELOCITY_COUNT),
                }
            ],
        }
    )
    layer = manifest.layers[0]
    assert manifest.name == "Piano"
    assert manifest.tempo == BANK_TEMPO
    assert layer.source.file == "instruments/module.it"
    assert layer.velocity_map is not None and layer.velocity_map.volume(100) == 17
    assert layer.select.covers(Expression(velocity=127, pitch=60))
    assert {Axis.VELOCITY, Axis.PITCH} == set(layer.select.root)


def test_a_layer_stating_only_its_source_answers_every_note() -> None:
    document = {
        "version": MANIFEST_VERSION,
        "name": "One",
        "tempo": BANK_TEMPO,
        "layers": [{"source": {"file": "module.it"}}],
    }
    layer = parsed(document).layers[0]
    assert layer.source.instrument == 0
    assert layer.velocity_map is None
    assert layer.select.covers(Expression(velocity=1, pitch=0))


def test_a_velocity_map_the_document_states_carries_its_own_measurement() -> None:
    """A producer measures the table against the very samples the layer stores, so the two are one unit.

    Stating the table in the document is what keeps a layer playing the dynamics its waveforms were
    written for, however the bank is copied or handed on.
    """
    volumes = list(range(VELOCITY_COUNT // 2)) * 2
    document = {
        "version": MANIFEST_VERSION,
        "name": "One",
        "tempo": BANK_TEMPO,
        "layers": [{"source": {"file": "module.it"}, "velocity_map": velocity_table(volumes)}],
    }
    layer = parsed(document).layers[0]
    assert layer.velocity_map is not None
    assert [layer.velocity_map.volume(velocity) for velocity in range(VELOCITY_COUNT)] == volumes


def test_a_velocity_table_of_another_shape_is_reported() -> None:
    document = {
        "version": MANIFEST_VERSION,
        "name": "One",
        "tempo": BANK_TEMPO,
        "layers": [{"source": {"file": "module.it"}, "velocity_map": {"volumes": [0, 1, 2]}}],
    }
    with pytest.raises(BankError, match="velocity_map"):
        parsed(document)


def test_an_axis_this_reader_does_not_name_is_reported() -> None:
    """A manifest routes on the axes stated here, so one naming another is refused rather than ignored."""
    document = {
        "version": MANIFEST_VERSION,
        "name": "One",
        "tempo": BANK_TEMPO,
        "layers": [{"source": {"file": "module.it"}, "select": {"aftertouch": {"low": 0, "high": 63}}}],
    }
    with pytest.raises(BankError, match="aftertouch"):
        parsed(document)


def test_a_field_a_later_producer_adds_still_loads() -> None:
    document = {
        "version": MANIFEST_VERSION,
        "name": "One",
        "tempo": BANK_TEMPO,
        "generator": "some future producer",
        "layers": [{"source": {"file": "module.it"}, "round_robin": 4}],
    }
    assert parsed(document).name == "One"


def test_a_manifest_of_another_version_is_reported() -> None:
    document = {
        "version": MANIFEST_VERSION + 1,
        "name": "One",
        "tempo": BANK_TEMPO,
        "layers": [{"source": {"file": "module.it"}}],
    }
    with pytest.raises(BankError, match="version"):
        parsed(document)


def test_a_bank_assembled_by_hand_states_no_tempo() -> None:
    """The clock is what a producer measured, so a bank written out of loose files leaves it open."""
    document = {"version": MANIFEST_VERSION, "name": "One", "layers": [{"source": {"file": "module.it"}}]}
    assert parsed(document).tempo is None


def test_a_manifest_naming_no_layer_is_reported() -> None:
    document = {"version": MANIFEST_VERSION, "name": "One", "tempo": BANK_TEMPO, "layers": []}
    with pytest.raises(BankError):
        parsed(document)


def test_the_bytes_a_manifest_could_not_be_are_reported_by_where_they_came_from() -> None:
    with pytest.raises(BankError, match=ORIGIN):
        BankManifest.parse(b"not a document", origin=ORIGIN)
