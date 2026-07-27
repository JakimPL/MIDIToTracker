from __future__ import annotations

from pathlib import Path

import pytest
from trackmod.core.notes.pitch import Note
from trackmod.limits.compliance import Compliance
from trackmod.trackers.xm.module import XMModule

from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.source import load_song, load_unit
from tests.conftest import instrument_file


def test_an_instrument_comes_out_with_the_samples_its_keys_reach(tmp_path: Path) -> None:
    unit = load_unit(instrument_file(tmp_path / "piano.it"), 0)
    assert len(unit.samples) == 1
    assert unit.instrument.assignment(Note.from_midi(60)) is not None


def test_a_key_the_instrument_leaves_unsampled_stays_unrouted(tmp_path: Path) -> None:
    unit = load_unit(instrument_file(tmp_path / "piano.it", keys=range(60, 64)), 0)
    assert unit.instrument.assignment(Note.from_midi(60)) is not None
    assert unit.instrument.assignment(Note.from_midi(59)) is None


def test_the_instrument_asked_for_is_the_one_taken(tmp_path: Path) -> None:
    unit = load_unit(instrument_file(tmp_path / "two.it", copies=2), 1)
    assert unit.instrument.name.endswith("1")


def test_either_format_a_module_is_written_as_reads_back(tmp_path: Path) -> None:
    # What a bank reads is independent of what a conversion writes, so both readers are registered and an
    # Impulse Tracker instrument is equally available to a module written as FastTracker 2.
    source = load_song(instrument_file(tmp_path / "piano.it"))
    written = tmp_path / "piano.xm"
    XMModule.from_song(source, compliance=Compliance.EXTENDED).save(written)
    assert len(load_unit(written, 0).samples) == 1


def test_a_file_of_no_format_a_bank_reads_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "piano.wav"
    path.write_bytes(b"RIFF")
    with pytest.raises(BankError, match="carries no extension"):
        load_unit(path, 0)


def test_a_file_that_is_not_there_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="does not read as an instrument file"):
        load_unit(tmp_path / "absent.it", 0)


def test_a_file_holding_no_such_instrument_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="names none of them"):
        load_unit(instrument_file(tmp_path / "piano.it"), 3)
