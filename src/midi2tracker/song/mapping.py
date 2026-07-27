from trackmod.spec.levels import MAX_VOLUME

from midi2tracker.spec import MAX_VELOCITY


def tracker_volume(velocity: int) -> int:
    """The volume column a MIDI velocity fills, on the tracker's own 0..64 scale."""
    return round(velocity * MAX_VOLUME / MAX_VELOCITY)
