from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from midi2tracker.arrangement.document import ArrangementDocument, arranges
from midi2tracker.arrangement.error import ArrangementError
from midi2tracker.arrangement.mode import ChannelAllocation

FIRST_TRACK = 0
SECOND_TRACK = 1


def written(path: Path, document: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_the_document_a_caller_writes_reads_back_whole(tmp_path: Path) -> None:
    document = ArrangementDocument.load(
        written(
            tmp_path / "song.yaml",
            {
                "name": "Suite",
                "clock": "brass.mid",
                "allocation": "packed",
                "tracks": {
                    "bass.mid": "Bass/Bass.bank",
                    "brass.mid": {"instrument_file": "Brass/Brass.iti", "channels": 8},
                },
            },
        )
    )
    assert document.name == "Suite"
    assert document.allocation is ChannelAllocation.PACKED
    assert document.timekeeper == SECOND_TRACK
    assert list(document.tracks) == [Path("bass.mid"), Path("brass.mid")]
    assert document.tracks[Path("bass.mid")].bank == Path("Bass/Bass.bank")
    assert document.tracks[Path("brass.mid")].channels == 8


def test_a_track_naming_a_path_alone_names_the_bank_it_plays_through(tmp_path: Path) -> None:
    # The common case is one bank per track, so it reads as the piece rather than as the model.
    document = ArrangementDocument.load(written(tmp_path / "song.yaml", {"tracks": {"bass.mid": "Bass.bank"}}))
    assert document.tracks[Path("bass.mid")].bank == Path("Bass.bank")


def test_a_track_stating_nothing_is_the_empty_slot(tmp_path: Path) -> None:
    document = ArrangementDocument.load(written(tmp_path / "song.yaml", {"tracks": {"drums.mid": None}}))
    spec = document.tracks[Path("drums.mid")]
    assert spec.bank is None and spec.instrument_file is None and spec.layers is None


def test_a_track_states_the_layers_a_bank_is_made_of(tmp_path: Path) -> None:
    document = ArrangementDocument.load(
        written(
            tmp_path / "song.yaml",
            {
                "tracks": {
                    "wood.mid": {
                        "name": "Woodwinds",
                        "layers": [
                            {"source": {"file": "soft.iti"}, "select": {"velocity": {"low": 0, "high": 63}}},
                            {"source": {"file": "loud.iti"}},
                        ],
                    }
                }
            },
        )
    )
    spec = document.tracks[Path("wood.mid")]
    assert spec.name == "Woodwinds"
    assert spec.layers is not None
    assert [layer.source.file for layer in spec.layers] == ["soft.iti", "loud.iti"]


def test_the_first_track_keeps_the_time_when_no_clock_is_named(tmp_path: Path) -> None:
    document = ArrangementDocument.load(
        written(tmp_path / "song.yaml", {"tracks": {"bass.mid": None, "brass.mid": None}})
    )
    assert document.clock is None
    assert document.timekeeper == FIRST_TRACK


def test_a_clock_naming_no_track_of_the_arrangement_is_reported(tmp_path: Path) -> None:
    document = {"clock": "absent.mid", "tracks": {"bass.mid": None}}
    with pytest.raises(ArrangementError, match="no track of this arrangement"):
        ArrangementDocument.load(written(tmp_path / "song.yaml", document))


def test_a_document_naming_no_track_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ArrangementError):
        ArrangementDocument.load(written(tmp_path / "song.yaml", {"tracks": {}}))


def test_a_document_that_states_nothing_at_all_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "song.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ArrangementError, match="does not read as an arrangement"):
        ArrangementDocument.load(path)


def test_a_document_that_is_not_there_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ArrangementError, match="does not read as an arrangement"):
        ArrangementDocument.load(tmp_path / "absent.yaml")


def test_a_document_that_is_not_yaml_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "song.yaml"
    path.write_text("tracks: [unclosed\n", encoding="utf-8")
    with pytest.raises(ArrangementError, match="does not read as an arrangement"):
        ArrangementDocument.load(path)


def test_a_document_naming_itself_goes_by_that_name(tmp_path: Path) -> None:
    document = ArrangementDocument.load(
        written(tmp_path / "song.yaml", {"name": "Suite", "tracks": {"bass.mid": None}})
    )
    assert document.name == "Suite"


def test_a_document_naming_nothing_goes_by_the_file_it_was_read_from(tmp_path: Path) -> None:
    document = ArrangementDocument.load(written(tmp_path / "suite.yaml", {"tracks": {"bass.mid": None}}))
    assert document.name == "suite"


def test_a_field_a_later_version_adds_still_loads(tmp_path: Path) -> None:
    document = {"swing": 0.6, "tracks": {"bass.mid": {"bank": "Bass.bank", "round_robin": 4}}}
    assert ArrangementDocument.load(written(tmp_path / "song.yaml", document)).tracks


def test_only_a_yaml_source_is_read_as_an_arrangement() -> None:
    assert arranges(".yaml") and arranges(".YML")
    assert not arranges(".mid")


def test_one_midi_file_is_the_same_document_written_the_short_way() -> None:
    """Converting one file is the single-track case, so it becomes a document rather than a second path."""
    document = ArrangementDocument.of(
        Path("song.mid"),
        bank=Path("Piano.bank"),
        instrument_file=None,
        velocity_map=None,
    )
    assert document.name == "song"
    assert document.timekeeper == FIRST_TRACK
    assert document.tracks[Path("song.mid")].bank == Path("Piano.bank")
