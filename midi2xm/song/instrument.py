"""The instrument every converted note plays through.

A MIDI file names an instrument but carries no waveform, so the module is written with an empty slot for
one: a zero-length sample the module reserves and a keymap that sends every key to it. Loading the file in
a tracker and dropping a real waveform into that slot is the intended last step, so the surrounding
settings are chosen for a sample that is not there yet.

The envelope is what makes that work. It holds at full volume for as long as the key is held and falls to
silence once it is released, which is what a sustaining instrument does — so a real waveform pasted into
the slot plays for the length the pattern grid says it should.
"""

from __future__ import annotations

import numpy as np
from trackmod.core.envelopes.envelope import Envelope
from trackmod.core.envelopes.point import EnvelopePoint
from trackmod.core.envelopes.span import EnvelopeSpan
from trackmod.core.instruments.instrument import Instrument
from trackmod.core.instruments.keymap import pitched_keymap
from trackmod.core.samples.sample import Sample
from trackmod.spec.levels import MAX_VOLUME

from midi2xm.spec import INSTRUMENT_NAME

DEFAULT_RATE = 44100
RELEASE_TICKS = 16  # how long the voice takes to fall silent once the key is released


def held_envelope() -> Envelope:
    """A volume envelope that holds while the key is down and fades once it is released.

    The sustain point sits on the full-volume breakpoint, so the curve waits there rather than running
    straight through to the silent one — which is what keeps a held note sounding.
    """
    return Envelope(
        points=(EnvelopePoint(tick=0, value=MAX_VOLUME), EnvelopePoint(tick=RELEASE_TICKS, value=0)),
        sustain=EnvelopeSpan(begin=0, end=0),
    )


def placeholder_sample(*, rate: int = DEFAULT_RATE) -> Sample:
    """The empty slot a real waveform is meant to replace, reserved at full volume and centred."""
    return Sample(name=INSTRUMENT_NAME, pcm=np.zeros(0), rate=rate, volume=MAX_VOLUME)


def placeholder_instrument(*, sample: int = 0) -> Instrument:
    """An instrument whose every key plays the reserved sample at that key's own pitch."""
    return Instrument(name=INSTRUMENT_NAME, keymap=pitched_keymap(sample=sample), volume_envelope=held_envelope())
