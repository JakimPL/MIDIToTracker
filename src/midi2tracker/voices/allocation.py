from dataclasses import dataclass, field

from midi2tracker.midi.events import MidiSong, NoteEvent
from midi2tracker.timing.grid import RowGrid
from midi2tracker.voices.voice import Voice


@dataclass(frozen=True)
class Allocation:
    """Every note placed on a channel, and how many of them had to displace another.

    ``stolen`` is the count of notes that arrived with no channel free; it is the measure of how much
    polyphony the chosen channel count cost the piece.
    """

    voices: tuple[Voice, ...]
    stolen: int

    @property
    def channels(self) -> int:
        """How many channels the piece actually reaches, at least one."""
        return max((voice.channel for voice in self.voices), default=0) + 1


@dataclass
class _Channel:
    """One channel's occupancy: the row its voice ends on, and the row that voice began."""

    ends: int = -1
    began: int = 0

    def free_at(self, row: int) -> bool:
        return self.ends <= row

    def take(self, *, began: int, ends: int) -> None:
        self.began = began
        self.ends = ends


@dataclass
class _Allocator:
    """The channel table, and the greedy rule that picks one for each note in turn."""

    channels: list[_Channel] = field(default_factory=list)
    stolen: int = 0

    def choose(self, row: int) -> int:
        """The channel to play a note starting on ``row``: the first free one, else the oldest voice's."""
        free = next((index for index, channel in enumerate(self.channels) if channel.free_at(row)), None)
        if free is not None:
            return free

        self.stolen += 1
        return min(
            range(len(self.channels)),
            key=lambda index: self.channels[index].began,
        )


def allocate(song: MidiSong, grid: RowGrid, *, channels: int) -> Allocation:
    """Place every note of ``song`` on one of ``channels`` channels, in the order the notes start."""
    allocator = _Allocator(channels=[_Channel() for _ in range(channels)])
    voices: list[Voice] = []
    for note in song.notes:
        voices.append(_placed(note, grid, allocator))

    return Allocation(voices=tuple(voices), stolen=allocator.stolen)


def _placed(note: NoteEvent, grid: RowGrid, allocator: _Allocator) -> Voice:
    start = grid.place(note.tick_on)
    release_row = grid.row_of(note.tick_off)
    channel = allocator.choose(start.row)
    allocator.channels[channel].take(began=start.row, ends=release_row)
    return Voice(
        note=note,
        channel=channel,
        start=start,
        release_row=release_row,
    )
