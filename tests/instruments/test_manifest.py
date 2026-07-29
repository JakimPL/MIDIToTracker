from __future__ import annotations

import json
from pathlib import Path

import pytest

from midi2tracker.instruments.axis import Axis
from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.manifest import MANIFEST_VERSION, BankManifest


def written(path: Path, document: dict[str, object]) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_the_document_a_producer_writes_reads_back_whole(tmp_path: Path) -> None:
    manifest = BankManifest.load(
        written(
            tmp_path / "bank.json",
            {
                "version": MANIFEST_VERSION,
                "name": "Piano",
                "layers": [
                    {
                        "source": {"file": "ungrouped/module.it", "instrument": 0},
                        "select": {"velocity": {"low": 0, "high": 127}, "pitch": {"low": 29, "high": 101}},
                        "velocity_map": "ungrouped/velocity_map.json",
                    }
                ],
            },
        )
    )
    layer = manifest.layers[0]
    assert manifest.name == "Piano"
    assert layer.source.file == Path("ungrouped/module.it")
    assert layer.velocity_map == Path("ungrouped/velocity_map.json")
    assert layer.select.covers(Expression(velocity=127, pitch=60))
    assert {Axis.VELOCITY, Axis.PITCH} == set(layer.select.root)


def test_a_layer_stating_only_its_source_answers_every_note(tmp_path: Path) -> None:
    document = {"version": MANIFEST_VERSION, "name": "One", "layers": [{"source": {"file": "module.it"}}]}
    layer = BankManifest.load(written(tmp_path / "bank.json", document)).layers[0]
    assert layer.source.instrument == 0
    assert layer.velocity_map is None
    assert layer.select.covers(Expression(velocity=1, pitch=0))


def test_an_axis_this_reader_does_not_name_is_reported(tmp_path: Path) -> None:
    """A manifest routes on the axes stated here, so one naming another is refused rather than ignored."""
    document = {
        "version": MANIFEST_VERSION,
        "name": "One",
        "layers": [{"source": {"file": "module.it"}, "select": {"aftertouch": {"low": 0, "high": 63}}}],
    }
    with pytest.raises(BankError, match="aftertouch"):
        BankManifest.load(written(tmp_path / "bank.json", document))


def test_a_field_a_later_producer_adds_still_loads(tmp_path: Path) -> None:
    document = {
        "version": MANIFEST_VERSION,
        "name": "One",
        "generator": "some future producer",
        "layers": [{"source": {"file": "module.it"}, "round_robin": 4}],
    }
    assert BankManifest.load(written(tmp_path / "bank.json", document)).name == "One"


def test_a_manifest_of_another_version_is_reported(tmp_path: Path) -> None:
    document = {"version": MANIFEST_VERSION + 1, "name": "One", "layers": [{"source": {"file": "module.it"}}]}
    with pytest.raises(BankError, match="version"):
        BankManifest.load(written(tmp_path / "bank.json", document))


def test_a_manifest_naming_no_layer_is_reported(tmp_path: Path) -> None:
    document = {"version": MANIFEST_VERSION, "name": "One", "layers": []}
    with pytest.raises(BankError):
        BankManifest.load(written(tmp_path / "bank.json", document))


def test_a_manifest_that_is_not_there_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="does not read as a bank manifest"):
        BankManifest.load(tmp_path / "absent.json")
