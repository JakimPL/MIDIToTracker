from trackmod.xm.spec.effects import TEMPO_PARAMETER

from midi2tracker.spec import TICKS_PER_BEAT


def tracker_tempo(
    beats_per_minute: float,
    *,
    speed: int,
    rows_per_beat: int,
) -> int:
    """The tracker tempo that plays ``beats_per_minute`` at this speed and row rate, before clamping."""
    return round(speed * beats_per_minute * rows_per_beat / TICKS_PER_BEAT)


def playable_tempo(
    beats_per_minute: float,
    *,
    speed: int,
    rows_per_beat: int,
) -> int:
    """The same tempo held to what the tempo effect's parameter byte can name.

    A tempo outside that range plays at the nearest one the byte reaches, so a piece too fast or too slow
    for the tracker still converts and simply plays at the speed it can.
    """
    tempo = tracker_tempo(
        beats_per_minute,
        speed=speed,
        rows_per_beat=rows_per_beat,
    )
    return max(
        TEMPO_PARAMETER.minimum,
        min(TEMPO_PARAMETER.maximum, tempo),
    )
