from __future__ import annotations

from trackmod.core.notes.pitch import Note
from trackmod.core.patterns.builder import PatternBuilder
from trackmod.core.songs.order import OrderList
from trackmod.core.songs.playback import Playback
from trackmod.core.songs.song import Song
from trackmod.limits.compliance import Compliance

from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.tracker.target import TrackerTarget
from tests.conftest import canonical

SILENT_ROWS = 32


def silent_song() -> Song:
    """A song both formats accept, so binding it says something about the target rather than the music."""
    return Song(
        name="silence",
        channels=2,
        patterns=(PatternBuilder(rows=SILENT_ROWS, channels=2).build(),),
        order=OrderList.sequential(1),
        instruments=(),
        samples=(),
        playback=Playback(speed=6, tempo=125),
    )


def test_a_song_binds_to_a_module_of_the_format_asked_for(target: TrackerTarget) -> None:
    module = target.bind(silent_song())
    assert module.extension == target.extension
    assert module.limits.compliance is target.compliance
    assert module.violations() == ()


def test_each_format_is_written_with_its_own_suffix() -> None:
    assert canonical(TrackerFormat.IT).extension == ".it"
    assert canonical(TrackerFormat.XM).extension == ".xm"


def test_the_two_formats_bound_a_module_differently() -> None:
    # These are the numbers every pass works to, and reading them from one place is what lets the passes
    # state what they need without naming a format.
    impulse, fast = canonical(TrackerFormat.IT), canonical(TrackerFormat.XM)
    assert (impulse.max_channels, impulse.max_rows, impulse.max_patterns) == (64, 200, 200)
    assert (fast.max_channels, fast.max_rows, fast.max_patterns) == (32, 256, 256)
    assert (impulse.max_instruments, fast.max_instruments) == (255, 128)


def test_extended_compliance_widens_what_a_format_carries(target: TrackerTarget) -> None:
    extended = TrackerTarget(format=target.format, compliance=Compliance.EXTENDED)
    assert extended.max_channels > target.max_channels


def test_the_row_floor_is_what_the_tracker_the_format_was_designed_for_reads() -> None:
    # Impulse Tracker itself reads patterns of at least 32 rows; the record layout holds shorter ones,
    # which is exactly what extended compliance allows.
    assert canonical(TrackerFormat.IT).min_rows == SILENT_ROWS
    assert TrackerTarget(format=TrackerFormat.IT, compliance=Compliance.EXTENDED).min_rows == 1
    assert canonical(TrackerFormat.XM).min_rows == 1


def test_each_format_spells_the_shared_effects_its_own_way() -> None:
    impulse, fast = canonical(TrackerFormat.IT), canonical(TrackerFormat.XM)
    assert impulse.effects.note_delay(3) != fast.effects.note_delay(3)
    assert impulse.effects.set_tempo(125) != fast.effects.set_tempo(125)


def test_a_row_is_divided_into_as_many_ticks_as_the_speed_effect_names(target: TrackerTarget) -> None:
    assert target.speed_parameter.contains(1)
    assert target.nibble_parameter.maximum == 15


def test_each_format_reaches_its_own_stretch_of_the_keyboard() -> None:
    # Impulse Tracker numbers all ten octaves and FastTracker 2 the lowest eight, so the top of a MIDI
    # keyboard lands on a key in one format and past the keys in the other.
    impulse, fast = canonical(TrackerFormat.IT), canonical(TrackerFormat.XM)
    assert impulse.carries(131) and impulse.carries(12)
    assert fast.carries(107) and fast.carries(12)
    assert not fast.carries(108)
    assert not impulse.carries(11)


def test_a_pitch_the_keyboard_reaches_keeps_the_octave_it_was_written_in(target: TrackerTarget) -> None:
    assert target.key(72) == Note.from_midi(72)
    assert target.key(72).octave == 5


def test_a_pitch_past_the_keyboard_sounds_on_the_nearest_key_there_is() -> None:
    fast = canonical(TrackerFormat.XM)
    assert fast.key(127) == Note(fast.keys.maximum)
    assert fast.key(0) == Note(fast.keys.minimum)
