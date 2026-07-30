from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from midi2tracker.arrangement.track import Track
from midi2tracker.midi.events import NoteEvent
from midi2tracker.settings import ChannelAllocation
from midi2tracker.timing.grid import RowGrid
from midi2tracker.tracker.target import TrackerTarget
from midi2tracker.voices.error import AllocationError
from midi2tracker.voices.voice import Voice

STEREO_PAIR: Final = 2
UNPLAYED: Final = -1  # the rows a channel that has carried no voice yet began and ended on


@dataclass(frozen=True)
class TrackAllocation:
    """What one track of a piece reached, and what its ceiling cost it.

    ``channels`` is how many voices the track ever sounds at once, which is the run of channels it takes
    when the tracks are kept apart and what it contributes to a shared pool. ``stolen`` counts the notes
    that arrived with the track already at its ceiling, each of which displaced the track's own oldest
    voice.
    """

    name: str
    channels: int
    stolen: int


@dataclass(frozen=True)
class Allocation:
    """Every note of a piece placed on a channel, and what each track reached getting there."""

    voices: tuple[Voice, ...]
    tracks: tuple[TrackAllocation, ...]

    @property
    def width(self) -> int:
        """How many channels the module declares: the ones the piece reaches, rounded up to a pair.

        Tracker channels are laid out in stereo pairs, so an odd count leaves a half-populated pair that
        some players and editors handle poorly.
        """
        reached = max((voice.channel for voice in self.voices), default=0) + 1
        return reached + reached % STEREO_PAIR

    @property
    def stolen(self) -> int:
        """How many notes of the whole piece displaced another, counted over every track."""
        return sum(track.stolen for track in self.tracks)


@dataclass
class _Channel:
    """One channel's occupancy: whose voice holds it, the row that voice ends on, and the row it began."""

    track: int = 0
    ends: int = UNPLAYED
    began: int = UNPLAYED

    def free_at(self, row: int) -> bool:
        """Whether a note starting on ``row`` can take this channel.

        The voice is done once its release row is reached, since the cell that starts a note also ends
        whatever the channel was playing, so a note may begin on the very row the previous one releases
        on. A voice that began on this row still holds the one cell that row has, so the channel answers
        the next note from the row after it.
        """
        return self.ends <= row and self.began < row

    def take(self, *, track: int, began: int, ends: int) -> None:
        self.track = track
        self.began = began
        self.ends = ends


@dataclass
class _Allocator:
    """One track's hold on the pool it draws from: the ceiling it stays within, and what it reached.

    A channel is free once the voice on it is off, whoever played it, so a shared pool lets one track
    sound where another has fallen silent. A track already at its ceiling gives up its own oldest voice
    rather than reaching for a channel another track holds, so a ceiling means the same thing however
    many tracks draw from the pool.
    """

    track: int
    ceiling: int
    pool: list[_Channel]
    stolen: int = 0
    reached: int = 0

    def choose(self, row: int) -> int:
        """The channel to play a note starting on ``row``: a free one, else this track's oldest voice."""
        sounding = [
            index for index, channel in enumerate(self.pool) if channel.track == self.track and not channel.free_at(row)
        ]
        if len(sounding) >= self.ceiling:
            self.stolen += 1
            return min(sounding, key=lambda index: self.pool[index].began)

        self.reached = max(self.reached, len(sounding) + 1)
        free = next((index for index, channel in enumerate(self.pool) if channel.free_at(row)), None)
        if free is not None:
            return free

        self.pool.append(_Channel())
        return len(self.pool) - 1


def _placed(note: NoteEvent, grid: RowGrid, allocator: _Allocator) -> Voice:
    start = grid.place(note.tick_on)
    release_row = grid.row_of(note.tick_off)
    channel = allocator.choose(start.row)
    allocator.pool[channel].take(track=allocator.track, began=start.row, ends=release_row)
    return Voice(
        note=note,
        track=allocator.track,
        channel=channel,
        start=start,
        release_row=release_row,
    )


def _in_order(tracks: Sequence[Track]) -> tuple[tuple[int, NoteEvent], ...]:
    """Every note of every track with the track it came from, in the order the notes start.

    Sorting keeps the tracks' own order where two notes begin on the same tick, so a piece reads the
    same however many files it was assembled from.
    """
    stated = [(index, note) for index, track in enumerate(tracks) for note in track.midi.notes]
    return tuple(sorted(stated, key=lambda placed: placed[1].tick_on))


def _voiced(tracks: Sequence[Track], grid: RowGrid, allocators: Sequence[_Allocator]) -> tuple[Voice, ...]:
    return tuple(_placed(note, grid, allocators[index]) for index, note in _in_order(tracks))


def _stated(tracks: Sequence[Track], allocators: Sequence[_Allocator], voices: tuple[Voice, ...]) -> Allocation:
    return Allocation(
        voices=voices,
        tracks=tuple(
            TrackAllocation(name=track.name, channels=allocator.reached, stolen=allocator.stolen)
            for track, allocator in zip(tracks, allocators, strict=True)
        ),
    )


def _packed(tracks: Sequence[Track], grid: RowGrid) -> Allocation:
    """Every track drawing from one pool, so a channel one track frees carries the next note of any.

    The tracks fill the gaps in each other's polyphony, which is what makes the piece span the channels
    it sounds at once rather than the channels it sounds altogether.
    """
    shared: list[_Channel] = []
    allocators = tuple(
        _Allocator(track=index, ceiling=track.channels, pool=shared) for index, track in enumerate(tracks)
    )
    return _stated(tracks, allocators, _voiced(tracks, grid, allocators))


def _separated(tracks: Sequence[Track], grid: RowGrid) -> Allocation:
    """Each track drawing from a pool of its own, the pools laid side by side in the order stated.

    A track's channels answer its own polyphony alone, so the module reads as the stems it was assembled
    from and spans as many channels as the tracks reach together.
    """
    allocators = tuple(_Allocator(track=index, ceiling=track.channels, pool=[]) for index, track in enumerate(tracks))
    voices = _voiced(tracks, grid, allocators)
    offsets = _side_by_side(allocators)
    return _stated(
        tracks,
        allocators,
        tuple(voice.model_copy(update={"channel": voice.channel + offsets[voice.track]}) for voice in voices),
    )


def _side_by_side(allocators: Sequence[_Allocator]) -> tuple[int, ...]:
    """Where each track's own pool begins, once every track has taken the channels it reached."""
    offsets: list[int] = []
    opening = 0
    for allocator in allocators:
        offsets.append(opening)
        opening += len(allocator.pool)

    return tuple(offsets)


_ALLOCATIONS: Final[Mapping[ChannelAllocation, Callable[[Sequence[Track], RowGrid], Allocation]]] = {
    ChannelAllocation.PACKED: _packed,
    ChannelAllocation.SEPARATED: _separated,
}


def _too_wide(
    tracks: Sequence[Track],
    grid: RowGrid,
    placed: Allocation,
    *,
    allocation: ChannelAllocation,
    target: TrackerTarget,
) -> str:
    """Why a piece spreads past the format, per track, and how wide the other way of sharing reaches."""
    other = ChannelAllocation.PACKED if allocation is ChannelAllocation.SEPARATED else ChannelAllocation.SEPARATED
    spread = ", ".join(f"{track.name} {track.channels}" for track in placed.tracks)
    return (
        f"{allocation} allocation reaches {placed.width} channels, where {target.format.upper()} plays "
        f"{target.max_channels}: {spread}; {other} allocation reaches "
        f"{_ALLOCATIONS[other](tracks, grid).width}"
    )


def allocate(
    tracks: Sequence[Track],
    grid: RowGrid,
    *,
    allocation: ChannelAllocation,
    target: TrackerTarget,
) -> Allocation:
    """Place every note of every track on a channel, in the order the notes start.

    ``allocation`` decides whether the tracks keep runs of channels of their own or draw from one pool
    between them, and each track allocates within the ceiling it states either way.

    Raises:
        AllocationError: when the piece reaches more channels than ``target`` plays.
    """
    placed = _ALLOCATIONS[allocation](tracks, grid)
    if placed.width > target.max_channels:
        raise AllocationError(_too_wide(tracks, grid, placed, allocation=allocation, target=target))

    return placed
