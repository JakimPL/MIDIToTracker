from __future__ import annotations

from pathlib import Path

import pytest
from trackmod.core.notes.pitch import Note
from trackmod.spec.levels import MAX_VOLUME
from trackmod.trackers.it.spec.identity import INSTRUMENT_EXTENSION as ITI_EXTENSION
from trackmod.trackers.xm.spec.identity import INSTRUMENT_EXTENSION as XI_EXTENSION

from midi2tracker.instruments.bank import Bank
from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.store import DirectoryStore, open_bank
from midi2tracker.instruments.velocity import VELOCITY_COUNT
from tests.conftest import (
    SAMPLED_KEYS,
    bank_manifest,
    instrument_file,
    standalone_instrument,
    velocity_map_file,
    velocity_table,
)

FIRST_LAYER = 0
MIDDLE_C = 60
STRUCK = Expression(velocity=100, pitch=MIDDLE_C)
STANDALONE = (ITI_EXTENSION, XI_EXTENSION)


def stored(path: Path, layers: list[dict[str, object]]) -> Bank:
    """The bank a manifest describes, read where a producer laid it out."""
    return Bank.from_store(DirectoryStore(path=bank_manifest(path, layers)))


def test_the_placeholder_is_one_layer_of_the_same_object() -> None:
    # The no-instrument path is a bank like any other, so nothing downstream has a second shape to serve.
    bank = Bank.placeholder()
    assert len(bank.units) == 1
    assert bank.voicing(Note.from_midi(60), STRUCK) is not None


def test_one_instrument_file_answers_every_note(tmp_path: Path) -> None:
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None)
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert voicing is not None
    assert voicing.slot == FIRST_LAYER
    assert voicing.volume == round(100 * MAX_VOLUME / 127)


def test_a_key_the_instrument_was_never_sampled_over_comes_out_silent(tmp_path: Path) -> None:
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None)
    outside = min(SAMPLED_KEYS) - 1
    assert bank.voicing(Note.from_midi(outside), STRUCK) is None


def test_a_velocity_map_sitting_beside_the_instrument_is_left_where_it_is(tmp_path: Path) -> None:
    """Naming an instrument alone reads velocity evenly, whatever else the directory happens to hold.

    What a run plays follows from what it was told, so a file it was never pointed at changes nothing —
    which is what keeps a conversion reproducible from its own settings.
    """
    velocity_map_file(tmp_path / "velocity_map.json", [7] * VELOCITY_COUNT)
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None)
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert voicing is not None and voicing.volume == round(100 * MAX_VOLUME / 127)


def test_a_velocity_map_stated_outright_is_the_one_read(tmp_path: Path) -> None:
    stated = velocity_map_file(tmp_path / "louder.json", [21] * VELOCITY_COUNT)
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=stated)
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert voicing is not None and voicing.volume == 21


def test_a_velocity_map_that_is_not_there_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="does not read as a velocity map"):
        Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=tmp_path / "absent.json")


def test_the_first_layer_covering_a_note_is_the_one_that_answers_it(tmp_path: Path) -> None:
    quiet = instrument_file(tmp_path / "quiet.it", name="Quiet")
    loud = instrument_file(tmp_path / "loud.it", name="Loud")
    bank = stored(
        tmp_path / "bank.json",
        [
            {"source": {"file": "quiet.it"}, "select": {"velocity": {"low": 0, "high": 63}}},
            {"source": {"file": "loud.it"}},
        ],
    )
    assert quiet.exists() and loud.exists()

    soft = bank.voicing(Note.from_midi(60), Expression(velocity=30, pitch=MIDDLE_C))
    hard = bank.voicing(Note.from_midi(60), Expression(velocity=100, pitch=MIDDLE_C))
    assert soft is not None and soft.slot == 0
    assert hard is not None and hard.slot == 1


def test_a_layer_of_one_band_is_reached_by_the_keys_it_states(tmp_path: Path) -> None:
    """Both instruments answer the same keys and the same dynamics, so the pitch band is what tells them apart.

    A producer whose format numbers few samples inside one instrument writes a band's keyboard across
    several, and each of them answers every key it was filled over, so the manifest states which of them
    owns which stretch.
    """
    instrument_file(tmp_path / "lower.it", name="Lower")
    instrument_file(tmp_path / "upper.it", name="Upper")
    bank = stored(
        tmp_path / "bank.json",
        [
            {"source": {"file": "lower.it"}, "select": {"pitch": {"low": 0, "high": 59}}},
            {"source": {"file": "upper.it"}, "select": {"pitch": {"low": 60, "high": 127}}},
        ],
    )

    lower = bank.voicing(Note.from_midi(55), Expression(velocity=100, pitch=55))
    upper = bank.voicing(Note.from_midi(60), STRUCK)
    assert lower is not None and lower.slot == 0
    assert upper is not None and upper.slot == 1


def test_a_layer_states_the_dynamics_and_the_keys_it_answers_together(tmp_path: Path) -> None:
    """A note reaches the layer whose every band covers it, so a split on both axes routes on both."""
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    instrument_file(tmp_path / "loud.it", name="Loud")
    bank = stored(
        tmp_path / "bank.json",
        [
            {
                "source": {"file": "quiet.it"},
                "select": {"velocity": {"low": 0, "high": 63}, "pitch": {"low": 60, "high": 127}},
            },
            {"source": {"file": "loud.it"}},
        ],
    )

    both = bank.voicing(Note.from_midi(60), Expression(velocity=30, pitch=MIDDLE_C))
    too_low = bank.voicing(Note.from_midi(55), Expression(velocity=30, pitch=55))
    too_hard = bank.voicing(Note.from_midi(60), STRUCK)
    assert both is not None and both.slot == 0
    assert too_low is not None and too_low.slot == 1
    assert too_hard is not None and too_hard.slot == 1


def test_every_layer_holds_the_instrument_its_entry_names(tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    instrument_file(tmp_path / "loud.it", name="Loud")
    bank = stored(tmp_path / "bank.json", [{"source": {"file": "quiet.it"}}, {"source": {"file": "loud.it"}}])
    assert [unit.instrument.name for unit in bank.units] == ["Quiet 0", "Loud 0"]
    assert [len(unit.samples) for unit in bank.units] == [1, 1]


def test_a_layer_reads_the_velocity_map_measured_for_it(tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    bank = stored(
        tmp_path / "bank.json",
        [{"source": {"file": "quiet.it"}, "velocity_map": velocity_table([11] * VELOCITY_COUNT)}],
    )
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert voicing is not None and voicing.volume == 11


def test_each_layer_reads_the_dynamics_it_was_measured_with(tmp_path: Path) -> None:
    # A producer measures a band against its own samples, so the maps differ between layers of one bank.
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    instrument_file(tmp_path / "loud.it", name="Loud")
    bank = stored(
        tmp_path / "bank.json",
        [
            {
                "source": {"file": "quiet.it"},
                "select": {"velocity": {"low": 0, "high": 63}},
                "velocity_map": velocity_table([11] * VELOCITY_COUNT),
            },
            {"source": {"file": "loud.it"}, "velocity_map": velocity_table([47] * VELOCITY_COUNT)},
        ],
    )

    soft = bank.voicing(Note.from_midi(60), Expression(velocity=30, pitch=MIDDLE_C))
    hard = bank.voicing(Note.from_midi(60), STRUCK)
    assert soft is not None and soft.volume == 11
    assert hard is not None and hard.volume == 47


def test_a_note_no_layer_covers_comes_out_silent(tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    bank = stored(
        tmp_path / "bank.json",
        [{"source": {"file": "quiet.it"}, "select": {"velocity": {"low": 0, "high": 63}}}],
    )
    assert bank.voicing(Note.from_midi(60), STRUCK) is None


def test_an_instrument_a_manifest_names_and_does_not_hold_is_reported(tmp_path: Path) -> None:
    with pytest.raises(BankError, match="absent.it"):
        stored(tmp_path / "bank.json", [{"source": {"file": "absent.it"}}])


def test_a_manifest_bank_goes_by_the_name_the_document_states(tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    assert stored(tmp_path / "bank.json", [{"source": {"file": "quiet.it"}}]).name == "Bank"


def test_one_instrument_file_goes_by_what_the_instrument_calls_itself(tmp_path: Path) -> None:
    source = instrument_file(tmp_path / "piano.it", name="Grand")
    assert Bank.from_instrument(source, velocity_map=None).name == "Grand 0"


def test_an_instrument_carrying_no_name_goes_by_the_file_it_came_out_of(tmp_path: Path) -> None:
    source = instrument_file(tmp_path / "piano.it", name="")
    assert Bank.from_instrument(source, velocity_map=None).name == "piano"


@pytest.mark.parametrize("suffix", STANDALONE)
def test_an_instrument_stored_on_its_own_is_a_bank_like_any_other(tmp_path: Path, suffix: str) -> None:
    source = standalone_instrument(tmp_path / f"piano{suffix}", name="Grand")
    bank = Bank.from_instrument(source, velocity_map=None)
    voicing = bank.voicing(Note.from_midi(60), STRUCK)
    assert bank.name == "Grand"
    assert voicing is not None and voicing.slot == FIRST_LAYER


@pytest.mark.parametrize("suffix", STANDALONE)
def test_a_manifest_layer_names_a_standalone_instrument_the_same_way(tmp_path: Path, suffix: str) -> None:
    # A reference is a file and a position within it, and a file holding one instrument is position zero.
    standalone_instrument(tmp_path / f"quiet{suffix}", name="Quiet")
    bank = stored(tmp_path / "bank.json", [{"source": {"file": f"quiet{suffix}"}}])
    assert bank.voicing(Note.from_midi(60), STRUCK) is not None


def test_the_entries_a_manifest_names_are_read_against_the_directory_it_sits_in(tmp_path: Path) -> None:
    # A producer writes the manifest beside what it produced, so a loose bank moves as one directory.
    inner = tmp_path / "ungrouped"
    inner.mkdir()
    instrument_file(inner / "module.it")
    bank = stored(tmp_path / "bank.json", [{"source": {"file": "ungrouped/module.it"}}])
    assert bank.voicing(Note.from_midi(60), STRUCK) is not None


def test_a_manifest_named_outright_is_read_where_it_sits(tmp_path: Path) -> None:
    instrument_file(tmp_path / "quiet.it", name="Quiet")
    path = bank_manifest(tmp_path / "bank.json", [{"source": {"file": "quiet.it"}}])
    assert Bank.from_store(open_bank(path)).name == "Bank"
