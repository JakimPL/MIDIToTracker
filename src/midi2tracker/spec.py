"""The fixed numbers this converter reads MIDI and the tracker clock against.

MIDI states a tempo as microseconds per quarter note; a tracker states one as a tick rate. The bridge
between them is :data:`TICKS_PER_BEAT`, the six ticks per row times four rows per beat that the tracker
clock was defined around, and every tempo conversion here runs through it.
"""

from __future__ import annotations

from typing import Final

SUSTAIN_CONTROLLER: Final = 64  # the MIDI controller number of the sustain pedal
PEDAL_DOWN: Final = 64  # a sustain controller at or above this value holds notes

MICROSECONDS_PER_MINUTE: Final = 60_000_000
DEFAULT_MICROSECONDS_PER_BEAT: Final = 500_000  # 120 BPM, what MIDI plays at when a file states no tempo

#: The tracker ticks one beat spans at its reference clock, which is what relates a musical tempo to the
#: beats-per-minute number a module header carries.
TICKS_PER_BEAT: Final = 24

MAX_PITCH: Final = 127
MAX_VELOCITY: Final = 127

MODULE_NAME: Final = "midi2tracker"
TRACKER_NAME: Final = "midi2tracker"
INSTRUMENT_NAME: Final = "Placeholder"
