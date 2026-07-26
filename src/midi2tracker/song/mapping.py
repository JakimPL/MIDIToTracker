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
