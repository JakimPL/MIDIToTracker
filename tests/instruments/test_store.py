from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from trackmod.core.notes.pitch import Note

from midi2tracker.instruments.bank import Bank
from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.store import (
    MANIFEST_NAME,
    ContainerStore,
    DirectoryStore,
    open_bank,
)
from midi2tracker.instruments.velocity import VELOCITY_COUNT
from tests.conftest import bank_container, bank_manifest, instrument_file, velocity_table

MIDDLE_C = 60
STRUCK = Expression(velocity=100, pitch=MIDDLE_C)


def test_a_bank_reads_the_same_whichever_way_it_was_shipped(tmp_path: Path) -> None:
    """A container and a directory are two packagings of one bank, so both give the same instruments.

    This is what lets a producer ship one file without a conversion learning a second kind of bank.
    """
    layers = [
        {"source": {"file": "instruments/quiet.it"}, "select": {"velocity": {"low": 0, "high": 63}}},
        {"source": {"file": "instruments/loud.it"}, "velocity_map": velocity_table([31] * VELOCITY_COUNT)},
    ]
    loose = tmp_path / "loose"
    (loose / "instruments").mkdir(parents=True)
    quiet = instrument_file(loose / "instruments" / "quiet.it", name="Quiet")
    loud = instrument_file(loose / "instruments" / "loud.it", name="Loud")
    spread = Bank.from_store(DirectoryStore(path=bank_manifest(loose / "bank.json", layers, name="Piano")))

    packed = Bank.from_store(
        ContainerStore(
            path=bank_container(
                tmp_path / "Piano.bank",
                layers,
                {"instruments/quiet.it": quiet, "instruments/loud.it": loud},
                name="Piano",
            )
        )
    )

    assert packed.name == spread.name
    assert [unit.instrument.name for unit in packed.units] == [unit.instrument.name for unit in spread.units]
    for expression in (Expression(velocity=30, pitch=MIDDLE_C), STRUCK):
        assert packed.voicing(Note.from_midi(MIDDLE_C), expression) == spread.voicing(
            Note.from_midi(MIDDLE_C), expression
        )


def test_a_container_carries_the_velocity_its_layers_were_measured_with(tmp_path: Path) -> None:
    # The map and the waveforms it was measured against travel as one file, which is the whole point.
    source = instrument_file(tmp_path / "quiet.it", name="Quiet")
    path = bank_container(
        tmp_path / "Piano.bank",
        [{"source": {"file": "quiet.it"}, "velocity_map": velocity_table([13] * VELOCITY_COUNT)}],
        {"quiet.it": source},
    )
    voicing = Bank.from_store(ContainerStore(path=path)).voicing(Note.from_midi(MIDDLE_C), STRUCK)
    assert voicing is not None and voicing.volume == 13


def test_a_container_names_the_store_that_reads_it(tmp_path: Path) -> None:
    source = instrument_file(tmp_path / "quiet.it", name="Quiet")
    path = bank_container(tmp_path / "Piano.bank", [{"source": {"file": "quiet.it"}}], {"quiet.it": source})
    assert isinstance(open_bank(path), ContainerStore)


def test_a_manifest_names_the_store_that_reads_it(tmp_path: Path) -> None:
    path = bank_manifest(tmp_path / "bank.json", [{"source": {"file": "quiet.it"}}])
    assert isinstance(open_bank(path), DirectoryStore)


def test_a_container_holding_no_manifest_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "Piano.bank"
    with zipfile.ZipFile(path, "w") as container:
        container.writestr("readme.txt", "nothing here")

    with pytest.raises(BankError, match=MANIFEST_NAME):
        ContainerStore(path=path).manifest()


def test_a_container_naming_an_entry_it_does_not_hold_is_reported(tmp_path: Path) -> None:
    path = bank_container(tmp_path / "Piano.bank", [{"source": {"file": "absent.it"}}], {})
    with pytest.raises(BankError, match="absent.it"):
        Bank.from_store(ContainerStore(path=path))


def test_a_file_that_is_no_container_at_all_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "Piano.bank"
    path.write_bytes(b"not an archive")
    with pytest.raises(BankError, match="does not read as a bank container"):
        ContainerStore(path=path).manifest()


def test_a_container_that_is_not_there_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="does not read as a bank container"):
        ContainerStore(path=tmp_path / "absent.bank").manifest()


def test_a_manifest_that_is_not_there_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="cannot be read"):
        DirectoryStore(path=tmp_path / "absent.json").manifest()


def test_an_entry_a_manifest_names_and_the_directory_lacks_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="absent.it"):
        Bank.from_store(DirectoryStore(path=bank_manifest(tmp_path / "bank.json", [{"source": {"file": "absent.it"}}])))
