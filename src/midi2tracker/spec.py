from typing import Final

SUSTAIN_CONTROLLER: Final = 64  # the MIDI controller number of the sustain pedal
PEDAL_DOWN: Final = 64  # a sustain controller at or above this value holds notes

MICROSECONDS_PER_MINUTE: Final = 60_000_000
DEFAULT_MICROSECONDS_PER_BEAT: Final = 500_000  # 120 BPM, what MIDI plays at when a file states no tempo
TICKS_PER_BEAT: Final = 24

MAX_PITCH: Final = 127
MAX_VELOCITY: Final = 127

MODULE_NAME: Final = "midi2tracker"
TRACKER_NAME: Final = "midi2tracker"
INSTRUMENT_NAME: Final = "Placeholder"
