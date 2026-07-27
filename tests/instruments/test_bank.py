from __future__ import annotations

import json
from pathlib import Path

import pytest
from trackmod.core.notes.pitch import Note
from trackmod.spec.levels import MAX_VOLUME

from midi2tracker.instruments.bank import Bank
from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.manifest import MANIFEST_VERSION
from midi2tracker.instruments.velocity import VELOCITY_COUNT
from tests.conftest import SAMPLED_KEYS, instrument_file, velocity_map_file

FIRST_SLOT = 0
STRUCK = Expression(velocity=100)


def manifest(path: Path, layers: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"version": MANIFEST_VERSION, "name": "Bank", "layers": layers}), encoding="utf-8")
    return path


def test_the_placeholder_is_one_layer_of_the_same_object() -> None:
    # The no-instrument path is a bank like any other, so nothing downstream has a second shape to serve.
    bank = Bank.placeholder(offset=FIRST_SLOT)
    instruments, samples = bank.content
    assert len(instruments) == 1 and len(samples) == 1
    assert bank.voicing(Note.from_midi(60), STRUCK) is not None


def test_one_instrument_file_answers_every_note(tmp_path: Path) -> None:
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None, offset=FIRST_SLOT)
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert voicing is not None
    assert voicing.slot == FIRST_SLOT
    assert voicing.volume == round(100 * MAX_VOLUME / 127)


def test_a_key_the_instrument_was_never_sampled_over_comes_out_silent(tmp_path: Path) -> None:
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None, offset=FIRST_SLOT)
    outside = min(SAMPLED_KEYS) - 1
    assert bank.voicing(Note.from_midi(outside), STRUCK) is None


def test_a_velocity_map_beside_the_instrument_is_picked_up(tmp_path: Path) -> None:
    # This is how a producer lays its output directory out, so the common case is one flag.
    velocity_map_file(tmp_path / "velocity_map.json", [7] * VELOCITY_COUNT)
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None, offset=FIRST_SLOT)
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert voicing is not None and voicing.volume == 7


def test_a_velocity_map_stated_outright_is_the_one_read(tmp_path: Path) -> None:
    velocity_map_file(tmp_path / "velocity_map.json", [7] * VELOCITY_COUNT)
    stated = velocity_map_file(tmp_path / "louder.json", [21] * VELOCITY_COUNT)
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=stated, offset=FIRST_SLOT)
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert voicing is not None and voicing.volume == 21


def test_the_layers_sit_on_the_slot_the_bank_starts_from(tmp_path: Path) -> None:
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None, offset=4)
    instruments, _ = bank.content
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert len(instruments) == 5
    assert all(assignment is None for instrument in instruments[:4] for assignment in instrument.keymap)
    assert voicing is not None and voicing.slot == 4


def test_the_first_layer_covering_a_note_is_the_one_that_answers_it(tmp_path: Path) -> None:
    quiet = instrument_file(tmp_path / "quiet.it", name="Quiet")
    loud = instrument_file(tmp_path / "loud.it", name="Loud")
    path = manifest(
        tmp_path / "bank.json",
        [
            {"source": {"file": "quiet.it"}, "select": {"velocity": {"low": 0, "high": 63}}},
            {"source": {"file": "loud.it"}},
        ],
    )
    bank = Bank.from_manifest(path, offset=FIRST_SLOT)
    assert quiet.exists() and loud.exists()

    soft = bank.voicing(Note.from_midi(60), Expression(velocity=30))
    hard = bank.voicing(Note.from_midi(60), Expression(velocity=100))
    assert soft is not None and soft.slot == 0
    assert hard is not None and hard.slot == 1


def test_every_layer_becomes_a_slot_with_its_own_samples_behind_it(tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    instrument_file(tmp_path / "loud.it", name="Loud")
    path = manifest(
        tmp_path / "bank.json",
        [{"source": {"file": "quiet.it"}}, {"source": {"file": "loud.it"}}],
    )
    instruments, samples = Bank.from_manifest(path, offset=FIRST_SLOT).content
    assert len(instruments) == 2 and len(samples) == 2
    assert [instrument.samples for instrument in instruments] == [(0,), (1,)]


def test_a_layer_reads_the_velocity_map_measured_for_it(tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    velocity_map_file(tmp_path / "quiet.json", [11] * VELOCITY_COUNT)
    path = manifest(
        tmp_path / "bank.json",
        [{"source": {"file": "quiet.it"}, "velocity_map": "quiet.json"}],
    )
    voicing = Bank.from_manifest(path, offset=FIRST_SLOT).voicing(Note.from_midi(60), STRUCK)
    assert voicing is not None and voicing.volume == 11


def test_a_note_no_layer_covers_comes_out_silent(tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    path = manifest(
        tmp_path / "bank.json",
        [{"source": {"file": "quiet.it"}, "select": {"velocity": {"low": 0, "high": 63}}}],
    )
    assert Bank.from_manifest(path, offset=FIRST_SLOT).voicing(Note.from_midi(60), STRUCK) is None


def test_an_instrument_a_manifest_names_and_does_not_hold_is_reported(tmp_path: Path) -> None:
    path = manifest(tmp_path / "bank.json", [{"source": {"file": "absent.it"}}])
    with pytest.raises(BankError, match="absent.it"):
        Bank.from_manifest(path, offset=FIRST_SLOT)


def test_the_paths_a_manifest_states_are_read_against_the_directory_it_sits_in(tmp_path: Path) -> None:
    # A producer writes the manifest beside what it produced, so a bank moves as one directory.
    inner = tmp_path / "ungrouped"
    inner.mkdir()
    instrument_file(inner / "module.it")
    path = manifest(tmp_path / "bank.json", [{"source": {"file": "ungrouped/module.it"}}])
    assert Bank.from_manifest(path, offset=FIRST_SLOT).voicing(Note.from_midi(60), STRUCK) is not None
