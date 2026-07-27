from typing import Final

import numpy as np
from trackmod.core.envelopes.envelope import Envelope
from trackmod.core.envelopes.point import EnvelopePoint
from trackmod.core.envelopes.span import EnvelopeSpan
from trackmod.core.instruments.instrument import Instrument
from trackmod.core.instruments.keymap import pitched_keymap, routed_keymap
from trackmod.core.instruments.unit import InstrumentUnit
from trackmod.core.samples.sample import Sample
from trackmod.spec.levels import MAX_VOLUME

from midi2tracker.spec import INSTRUMENT_NAME

DEFAULT_RATE: Final = 44100
RELEASE_TICKS: Final = 16
FIRST_SAMPLE: Final = 0


def held_envelope() -> Envelope:
    """A volume envelope that holds while the key is down and fades once it is released.

    The sustain point sits on the full-volume breakpoint, so the curve waits there rather than running
    straight through to the silent one — which is what keeps a held note sounding.
    """
    return Envelope(
        points=(
            EnvelopePoint(tick=0, value=MAX_VOLUME),
            EnvelopePoint(tick=RELEASE_TICKS, value=0),
        ),
        sustain=EnvelopeSpan(begin=0, end=0),
    )


def placeholder_sample(*, rate: int = DEFAULT_RATE) -> Sample:
    """The empty slot a real waveform is meant to replace, reserved at full volume and centred."""
    return Sample(
        name=INSTRUMENT_NAME,
        pcm=np.zeros(0),
        rate=rate,
        volume=MAX_VOLUME,
    )


def placeholder_instrument() -> Instrument:
    """An instrument whose every key plays the reserved sample at that key's own pitch."""
    return Instrument(
        name=INSTRUMENT_NAME,
        keymap=pitched_keymap(sample=FIRST_SAMPLE),
        volume_envelope=held_envelope(),
    )


def placeholder_unit() -> InstrumentUnit:
    """The empty slot as a bank holds it: the instrument, and the reserved sample its keys name.

    A conversion pointed at no instrument writes this, so the module opens in a tracker with one slot
    waiting for a waveform and the piece already laid out around it.
    """
    return InstrumentUnit(instrument=placeholder_instrument(), samples=(placeholder_sample(),))


def reserved_unit() -> InstrumentUnit:
    """A slot a tracker numbers and nothing reaches: an instrument routing no key to a sample.

    Placing a bank on a chosen slot means the slots below it exist, and this is what they hold.
    """
    return InstrumentUnit(instrument=Instrument(name="", keymap=routed_keymap({})), samples=())
