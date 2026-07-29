from __future__ import annotations

from pathlib import Path

from midi2tracker.arrangement.mode import DEFAULT_ALLOCATION
from midi2tracker.instruments.bank import Bank
from midi2tracker.instruments.ensemble import Ensemble
from midi2tracker.midi.events import NoteEvent
from midi2tracker.song.sounding import Sounding, sound
from midi2tracker.timing.grid import RowGrid
from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.tracker.target import TrackerTarget
from midi2tracker.voices.allocation import allocate
from tests.conftest import SAMPLED_KEYS, canonical, instrument_file, midi_song, note, track

PLACEHOLDER_SLOT = 0
NO_RESERVE = 0


def sounding(grid: RowGrid, *notes: NoteEvent, bank: Bank, target: TrackerTarget) -> Sounding:
    """One song read through a bank, which is what decides the cells before any grid is touched."""
    ensemble = Ensemble.of((bank,), reserved=NO_RESERVE)
    allocation = allocate(
        (track(midi_song(*notes), channels=4),),
        grid,
        allocation=DEFAULT_ALLOCATION,
        target=target,
    )
    return sound(allocation, ensemble=ensemble, target=target)


def test_every_note_a_bank_answers_carries_its_slot_and_volume(grid: RowGrid, target: TrackerTarget) -> None:
    bank = Bank.placeholder()
    result = sounding(grid, note(0, 48, pitch=60, velocity=100), bank=bank, target=target)
    assert len(result.sounded) == 1
    assert result.sounded[0].voicing.slot == PLACEHOLDER_SLOT
    assert result.sounded[0].voicing.volume > 0
    assert result.unplayable == () and result.silent == ()


def test_a_note_past_the_keys_the_format_numbers_is_named_rather_than_moved(grid: RowGrid) -> None:
    # FastTracker 2 stops eight octaves up, and sounding the note an octave down would put a wrong pitch
    # in the piece where reporting it lets the caller choose a format that reaches further.
    fast = canonical(TrackerFormat.XM)
    bank = Bank.placeholder()
    result = sounding(grid, note(0, 48, pitch=120), bank=bank, target=fast)
    assert result.sounded == ()
    assert [event.pitch for event in result.unplayable] == [120]
    assert result.silent == ()


def test_the_same_note_sounds_where_the_format_numbers_a_key_for_it(grid: RowGrid) -> None:
    impulse = canonical(TrackerFormat.IT)
    result = sounding(grid, note(0, 48, pitch=120), bank=Bank.placeholder(), target=impulse)
    assert len(result.sounded) == 1
    assert result.unplayable == ()


def test_a_note_the_bank_never_sampled_is_named_rather_than_dropped_in_silence(
    grid: RowGrid,
    target: TrackerTarget,
    tmp_path: Path,
) -> None:
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None)
    outside = min(SAMPLED_KEYS) - 1
    result = sounding(grid, note(0, 48, pitch=outside), bank=bank, target=target)
    assert result.sounded == ()
    assert [event.pitch for event in result.silent] == [outside]
    assert result.unplayable == ()


def test_the_two_silences_are_counted_apart(grid: RowGrid, tmp_path: Path) -> None:
    # One is corrected by writing another format and the other by sampling more widely, so a run says
    # which happened rather than reporting a single count of missing notes.
    fast = canonical(TrackerFormat.XM)
    bank = Bank.from_instrument(instrument_file(tmp_path / "piano.it"), velocity_map=None)
    result = sounding(
        grid,
        note(0, 48, pitch=120),
        note(96, 48, pitch=min(SAMPLED_KEYS) - 1),
        note(192, 48, pitch=60),
        bank=bank,
        target=fast,
    )
    assert [event.pitch for event in result.unplayable] == [120]
    assert [event.pitch for event in result.silent] == [min(SAMPLED_KEYS) - 1]
    assert len(result.sounded) == 1
