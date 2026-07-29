from __future__ import annotations

from pathlib import Path

from trackmod.core.notes.pitch import Note

from midi2tracker.instruments.bank import Bank
from midi2tracker.instruments.ensemble import Ensemble
from midi2tracker.instruments.expression import Expression
from midi2tracker.instruments.store import DirectoryStore
from midi2tracker.instruments.velocity import VELOCITY_COUNT
from tests.conftest import bank_manifest, instrument_file, velocity_table

MIDDLE_C = 60
STRUCK = Expression(velocity=100, pitch=MIDDLE_C)
NO_RESERVE = 0
FIRST_TRACK = 0
SECOND_TRACK = 1


def layered(path: Path, *, name: str, volume: int) -> Bank:
    """A bank of two layers split on velocity, which is what a producer of a sampled instrument writes."""
    directory = path.parent
    instrument_file(directory / f"{name}-quiet.it", name=f"{name} quiet")
    instrument_file(directory / f"{name}-loud.it", name=f"{name} loud")
    return Bank.from_store(
        DirectoryStore(
            path=bank_manifest(
                path,
                [
                    {
                        "source": {"file": f"{name}-quiet.it"},
                        "select": {"velocity": {"low": 0, "high": 63}},
                    },
                    {
                        "source": {"file": f"{name}-loud.it"},
                        "velocity_map": velocity_table([volume] * VELOCITY_COUNT),
                    },
                ],
                name=name,
            )
        )
    )


def test_one_bank_starts_where_the_reserve_leaves_off(tmp_path: Path) -> None:
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None)
    ensemble = Ensemble.of((bank,), reserved=4)
    instruments, _ = ensemble.content
    voicing = ensemble.voicing(FIRST_TRACK, Note.from_midi(MIDDLE_C), STRUCK)
    assert len(instruments) == 5
    assert all(assignment is None for instrument in instruments[:4] for assignment in instrument.keymap)
    assert voicing is not None and voicing.slot == 4


def test_each_bank_takes_the_slots_after_the_one_before_it(tmp_path: Path) -> None:
    first = layered(tmp_path / "first.json", name="First", volume=11)
    second = layered(tmp_path / "second.json", name="Second", volume=47)
    ensemble = Ensemble.of((first, second), reserved=NO_RESERVE)
    instruments, samples = ensemble.content

    assert [placement.offset for placement in ensemble.placements] == [0, 2]
    assert len(instruments) == 4 and len(samples) == 4
    assert [instrument.samples for instrument in instruments] == [(0,), (1,), (2,), (3,)]


def test_a_note_sounds_through_the_bank_its_own_track_plays(tmp_path: Path) -> None:
    first = layered(tmp_path / "first.json", name="First", volume=11)
    second = layered(tmp_path / "second.json", name="Second", volume=47)
    ensemble = Ensemble.of((first, second), reserved=NO_RESERVE)

    leading = ensemble.voicing(FIRST_TRACK, Note.from_midi(MIDDLE_C), STRUCK)
    following = ensemble.voicing(SECOND_TRACK, Note.from_midi(MIDDLE_C), STRUCK)
    assert leading is not None and leading.slot == 1 and leading.volume == 11
    assert following is not None and following.slot == 3 and following.volume == 47


def test_two_tracks_playing_one_bank_share_its_slots(tmp_path: Path) -> None:
    """A bank two tracks name costs one set of instruments and stores its samples once.

    Sharing is what keeps a piece assembled from stems of the same instrument the size of the instrument
    rather than the size of the stems.
    """
    shared = layered(tmp_path / "shared.json", name="Shared", volume=11)
    ensemble = Ensemble.of((shared, shared), reserved=NO_RESERVE)
    instruments, samples = ensemble.content

    assert len(ensemble.placements) == 1
    assert ensemble.tracks == (0, 0)
    assert len(instruments) == 2 and len(samples) == 2
    assert ensemble.voicing(FIRST_TRACK, Note.from_midi(MIDDLE_C), STRUCK) == ensemble.voicing(
        SECOND_TRACK, Note.from_midi(MIDDLE_C), STRUCK
    )


def test_the_banks_a_piece_plays_are_the_distinct_ones(tmp_path: Path) -> None:
    first = layered(tmp_path / "first.json", name="First", volume=11)
    shared = layered(tmp_path / "shared.json", name="Shared", volume=47)
    ensemble = Ensemble.of((first, shared, shared), reserved=NO_RESERVE)
    assert [bank.name for bank in ensemble.banks] == ["First", "Shared"]
    assert ensemble.tracks == (0, 1, 1)


def test_a_key_a_track_s_bank_never_sampled_stays_silent(tmp_path: Path) -> None:
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it", keys=range(60, 64)), velocity_map=None)
    ensemble = Ensemble.of((bank,), reserved=NO_RESERVE)
    assert ensemble.voicing(FIRST_TRACK, Note.from_midi(59), Expression(velocity=100, pitch=59)) is None
