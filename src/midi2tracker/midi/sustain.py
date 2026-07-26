from dataclasses import dataclass, field

from midi2tracker.midi.events import NoteEvent


@dataclass
class SustainedVoices:
    """The keys currently sounding, and which of them are held by the pedal rather than by a finger.

    Notes are collected as they close, so the caller reads :attr:`closed` once the whole file has been
    walked rather than threading a list through every call.
    """

    pedal_down: bool = False
    closed: list[NoteEvent] = field(default_factory=list)
    _held: dict[int, tuple[int, int]] = field(default_factory=dict)  # pitch -> (tick_on, velocity)
    _pedalled: set[int] = field(default_factory=set)

    def press(self, pitch: int, tick: int, velocity: int) -> None:
        """Start a voice, ending the pedal-held one on the same key first."""
        if pitch in self._pedalled:
            self._pedalled.discard(pitch)
            self._close(pitch, tick)

        self._held[pitch] = (tick, velocity)

    def release(self, pitch: int, tick: int) -> None:
        """Let go of a key: the voice ends now, or waits for the pedal when the pedal is down."""
        if self.pedal_down:
            self._pedalled.add(pitch)
        else:
            self._close(pitch, tick)

    def pedal(self, *, down: bool, tick: int) -> None:
        """Move the pedal, ending every voice it was holding when it lifts."""
        self.pedal_down = down
        if down:
            return

        for pitch in sorted(self._pedalled):
            self._close(pitch, tick)

        self._pedalled.clear()

    def finish(self, *, tick: int, minimum: int) -> list[NoteEvent]:
        """Close every voice still sounding at the end of the file and return all the notes collected.

        A file may simply stop while keys are down. Those voices end at ``tick``, or ``minimum`` ticks
        after they started when that is later, so a note the file never released still sounds long enough
        to be heard rather than collapsing to nothing.
        """
        for pitch in sorted(self._held):
            self._close(pitch, max(tick, self._held[pitch][0] + minimum))

        self._pedalled.clear()
        return sorted(self.closed, key=lambda note: (note.tick_on, note.pitch))

    def _close(self, pitch: int, tick: int) -> None:
        started = self._held.pop(pitch, None)
        if started is None:
            return

        tick_on, velocity = started
        self.closed.append(
            NoteEvent(
                tick_on=tick_on,
                tick_off=max(tick, tick_on),
                pitch=pitch,
                velocity=velocity,
            )
        )
