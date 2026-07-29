from __future__ import annotations

from pathlib import Path

import pytest
from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.core.notes.pitch import Note
from trackmod.limits.compliance import Compliance
from trackmod.trackers.it.module import ITModule
from trackmod.trackers.it.spec.identity import INSTRUMENT_EXTENSION as ITI_EXTENSION
from trackmod.trackers.xm.module import XMModule
from trackmod.trackers.xm.spec.identity import INSTRUMENT_EXTENSION as XI_EXTENSION

from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.source import parse_units, read_units, select_unit
from tests.conftest import SAMPLED_KEYS, instrument_file, standalone_instrument

FIRST_INSTRUMENT = 0
STANDALONE = (ITI_EXTENSION, XI_EXTENSION)


def loaded(path: Path, index: int = FIRST_INSTRUMENT) -> InstrumentUnit:
    """One instrument out of a file on disk, which is how a stated instrument file is read."""
    return select_unit(read_units(path), index, origin=str(path))


def test_an_instrument_comes_out_with_the_samples_its_keys_reach(tmp_path: Path) -> None:
    unit = loaded(instrument_file(tmp_path / "piano.it"))
    assert len(unit.samples) == 1
    assert unit.instrument.assignment(Note.from_midi(60)) is not None


def test_a_key_the_instrument_leaves_unsampled_stays_unrouted(tmp_path: Path) -> None:
    unit = loaded(instrument_file(tmp_path / "piano.it", keys=range(60, 64)))
    assert unit.instrument.assignment(Note.from_midi(60)) is not None
    assert unit.instrument.assignment(Note.from_midi(59)) is None


def test_the_instrument_asked_for_is_the_one_taken(tmp_path: Path) -> None:
    unit = loaded(instrument_file(tmp_path / "two.it", copies=2), 1)
    assert unit.instrument.name.endswith("1")


def test_either_format_a_module_is_written_as_reads_back(tmp_path: Path) -> None:
    # What a bank reads is independent of what a conversion writes, so both readers are registered and an
    # Impulse Tracker instrument is equally available to a module written as FastTracker 2.
    source = ITModule.load(instrument_file(tmp_path / "piano.it")).song
    written = tmp_path / "piano.xm"
    XMModule.from_song(source, compliance=Compliance.EXTENDED).save(written)
    assert len(loaded(written).samples) == 1


def test_bytes_read_the_same_way_a_file_does(tmp_path: Path) -> None:
    # A bank shipped as one archive holds its instruments as entries, so the bytes are what reaches here.
    path = instrument_file(tmp_path / "piano.it")
    units = parse_units(path.read_bytes(), extension=".it", origin="instruments/piano.it")
    assert [unit.instrument.name for unit in units] == [unit.instrument.name for unit in read_units(path)]


def test_an_extension_is_matched_however_it_is_capitalised(tmp_path: Path) -> None:
    path = instrument_file(tmp_path / "piano.it")
    assert len(parse_units(path.read_bytes(), extension=".IT", origin="piano.IT")) == 1


@pytest.mark.parametrize("suffix", STANDALONE)
def test_an_instrument_stored_on_its_own_reads_like_one_out_of_a_module(tmp_path: Path, suffix: str) -> None:
    source = standalone_instrument(tmp_path / f"piano{suffix}", name="Grand")
    unit = loaded(source)
    assert unit.instrument.name == "Grand"
    assert len(unit.samples) == 1
    assert unit.instrument.assignment(Note(min(SAMPLED_KEYS))) is not None


@pytest.mark.parametrize("suffix", STANDALONE)
def test_a_standalone_file_holds_the_one_instrument_it_is(tmp_path: Path, suffix: str) -> None:
    source = standalone_instrument(tmp_path / f"piano{suffix}")
    assert len(read_units(source)) == 1
    with pytest.raises(BankError, match="names none of them"):
        loaded(source, 1)


@pytest.mark.parametrize("suffix", STANDALONE)
def test_a_standalone_file_carrying_another_format_is_reported(tmp_path: Path, suffix: str) -> None:
    # A suffix a reader answers to says nothing about the bytes, so the tag inside is what decides.
    path = tmp_path / f"claimed{suffix}"
    path.write_bytes(instrument_file(tmp_path / "piano.it").read_bytes())
    with pytest.raises(BankError, match="does not read as an instrument file"):
        loaded(path)


def test_a_file_of_no_format_a_bank_reads_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "piano.wav"
    path.write_bytes(b"RIFF")
    with pytest.raises(BankError, match="carries no extension"):
        loaded(path)


def test_a_file_that_is_not_there_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="does not read as an instrument file"):
        loaded(tmp_path / "absent.it")


def test_a_file_holding_no_such_instrument_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="names none of them"):
        loaded(instrument_file(tmp_path / "piano.it"), 3)
