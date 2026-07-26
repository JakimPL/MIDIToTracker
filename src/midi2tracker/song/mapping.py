"""Turning one MIDI note's numbers into the ones a pattern cell carries.

Both scales are the same idea counted differently. A tracker numbers its keyboard from C-0 where MIDI
numbers the same pitch an octave higher, so a key is a fixed shift away; and a tracker's volume column
runs 0..64 where MIDI velocity runs 0..127, so a struck note's force is a rescale.

Where the two ranges part company is at the ends of the keyboard: MIDI reaches notes below and above the
keys this format numbers, and those play at the nearest key it has rather than being dropped.
"""

from __future__ import annotations

from trackmod.core.notes.pitch import Note
from trackmod.spec.levels import MAX_VOLUME
from trackmod.xm.spec.ranges import MAX_NOTE

from midi2tracker.spec import MAX_VELOCITY


def tracker_note(pitch: int) -> Note:
    """The key a MIDI pitch is played on, held to the keys this format numbers."""
    return Note(max(0, min(MAX_NOTE, Note.from_midi(pitch).value)))


def tracker_volume(velocity: int) -> int:
    """The volume column a MIDI velocity fills, on the tracker's own 0..64 scale."""
    return round(velocity * MAX_VOLUME / MAX_VELOCITY)
