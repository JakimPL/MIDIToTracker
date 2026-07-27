from trackmod.limits.bound import Bound

from midi2tracker.timing.tempo import tracker_tempo
from midi2tracker.tracker.target import TrackerTarget


def speed_bound(target: TrackerTarget) -> Bound:
    """The speeds a row is divided into: what the speed effect names, held to what a note delay addresses.

    A row divided into more ticks than a delay can name holds positions no cell could express, so the
    nibble the delay travels in is the ceiling wherever it falls below the speed effect's own.
    """
    return Bound(
        minimum=target.speed_parameter.minimum,
        maximum=min(target.nibble_parameter.maximum + 1, target.speed_parameter.maximum),
    )


def select_speed(
    fastest: float,
    rows_per_beat: int,
    *,
    target: TrackerTarget,
) -> int:
    """The largest speed at which the piece's fastest tempo still fits the tempo effect's parameter.

    Falls back to the slowest usable speed when a tempo is high enough that even one tick a row overruns
    the parameter, so the conversion still produces a module — the tempo is then clamped, and the piece
    plays slower than it was written.
    """
    speeds = speed_bound(target)
    reachable = target.tempo_parameter.maximum
    for speed in range(speeds.maximum, speeds.minimum, -1):
        if tracker_tempo(fastest, speed=speed, rows_per_beat=rows_per_beat) <= reachable:
            return speed

    return speeds.minimum
