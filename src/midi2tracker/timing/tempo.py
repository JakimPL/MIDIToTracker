"""Converting a musical tempo into the number a tracker header and its tempo effect carry.

A tracker's tempo is a tick rate, not a beat rate: it says how fast the ticks pass, and how many of them
a row spends is the speed. Turning a musical beats-per-minute figure into it therefore takes both the
speed and how many rows a beat is spread over.

The result is held to the range the tempo *effect* can name, one byte, even for the opening tempo the
header could hold more of. A piece whose speed changes mid-song has to express those changes as effects,
so a header value the effects cannot reach would make the opening tempo unrecoverable after the first
change.
"""

from __future__ import annotations

from trackmod.xm.spec.effects import TEMPO_PARAMETER

from midi2tracker.spec import TICKS_PER_BEAT


def tracker_tempo(beats_per_minute: float, *, speed: int, rows_per_beat: int) -> int:
    """The tracker tempo that plays ``beats_per_minute`` at this speed and row rate, before clamping."""
    return round(speed * beats_per_minute * rows_per_beat / TICKS_PER_BEAT)


def playable_tempo(beats_per_minute: float, *, speed: int, rows_per_beat: int) -> int:
    """The same tempo held to what the tempo effect's parameter byte can name.

    A tempo outside that range plays at the nearest one the byte reaches, so a piece too fast or too slow
    for the tracker still converts and simply plays at the speed it can.
    """
    tempo = tracker_tempo(beats_per_minute, speed=speed, rows_per_beat=rows_per_beat)
    return max(TEMPO_PARAMETER.minimum, min(TEMPO_PARAMETER.maximum, tempo))
