"""Choosing how many tracker ticks a row lasts.

Speed and tempo scale together: a row keeps the same duration when both double, so raising the speed buys
sub-row resolution rather than changing the music. Two ceilings decide how far that can go. The tempo the
tracker reads is one byte, so the fastest passage in the piece has to stay under it; and a note delay is
one nibble, so a row divided into more than sixteen ticks has positions no cell can name.

The speed chosen here is therefore the largest that respects both, which is the finest placement this
conversion can express.
"""

from __future__ import annotations

from trackmod.xm.spec.effects import NIBBLE_PARAMETER, SPEED_PARAMETER, TEMPO_PARAMETER

from midi2xm.timing.tempo import tracker_tempo

#: The most ticks a row can hold and still have every position inside it nameable by a note delay.
ADDRESSABLE_SPEED = NIBBLE_PARAMETER.maximum + 1

MAX_SPEED = min(ADDRESSABLE_SPEED, SPEED_PARAMETER.maximum)
MIN_SPEED = SPEED_PARAMETER.minimum


def select_speed(fastest: float, rows_per_beat: int) -> int:
    """The largest speed at which the piece's fastest tempo still fits the tracker's tempo byte.

    Falls back to the slowest usable speed when a tempo is high enough that even one tick a row overruns
    the byte, so the conversion still produces a module — the tempo is then clamped, and the piece plays
    slower than it was written.
    """
    for speed in range(MAX_SPEED, MIN_SPEED, -1):
        if tracker_tempo(fastest, speed=speed, rows_per_beat=rows_per_beat) <= TEMPO_PARAMETER.maximum:
            return speed

    return MIN_SPEED
