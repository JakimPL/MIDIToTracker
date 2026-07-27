from trackmod.trackers.xm.spec.effects import NIBBLE_PARAMETER, SPEED_PARAMETER, TEMPO_PARAMETER

from midi2tracker.timing.tempo import tracker_tempo

ADDRESSABLE_SPEED = NIBBLE_PARAMETER.maximum + 1

MAX_SPEED = min(ADDRESSABLE_SPEED, SPEED_PARAMETER.maximum)
MIN_SPEED = SPEED_PARAMETER.minimum


def select_speed(
    fastest: float,
    rows_per_beat: int,
) -> int:
    """The largest speed at which the piece's fastest tempo still fits the tracker's tempo byte.

    Falls back to the slowest usable speed when a tempo is high enough that even one tick a row overruns
    the byte, so the conversion still produces a module — the tempo is then clamped, and the piece plays
    slower than it was written.
    """
    for speed in range(MAX_SPEED, MIN_SPEED, -1):
        if tracker_tempo(fastest, speed=speed, rows_per_beat=rows_per_beat) <= TEMPO_PARAMETER.maximum:
            return speed

    return MIN_SPEED
