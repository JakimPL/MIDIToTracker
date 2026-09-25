from dataclasses import dataclass

from trackmod.core.songs.order import OrderList
from trackmod.core.songs.playback import Playback
from trackmod.core.songs.song import Song

from midi2tracker.arrangement.piece import Arrangement
from midi2tracker.midi.events import NoteEvent, TempoEvent
from midi2tracker.song.height import pattern_height
from midi2tracker.song.layout import Layout
from midi2tracker.song.patterns import Grids, build_patterns
from midi2tracker.song.report import TrackReport, report
from midi2tracker.song.sounding import sound
from midi2tracker.timing.grid import RowGrid
from midi2tracker.timing.tempo import playable_tempo
from midi2tracker.tracker.target import TrackerTarget
from midi2tracker.voices.allocation import Allocation

TRAILING_BEATS = 1


@dataclass(frozen=True)
class Conversion:
    """One converted piece: the song, what each track cost, and the tempo changes the grid had no room for.

    ``tracks`` is where every loss is kept, since each one is corrected in the track that earned it; the
    counts below read the same account over the whole piece.
    """

    song: Song
    tracks: tuple[TrackReport, ...]
    dropped_tempos: tuple[TempoEvent, ...]

    @property
    def rows(self) -> int:
        """How many rows the song plays through."""
        return self.song.rows

    @property
    def stolen_notes(self) -> int:
        """How many notes of the piece displaced another, counted over every track."""
        return sum(track.stolen for track in self.tracks)

    @property
    def unplayable_notes(self) -> tuple[NoteEvent, ...]:
        """Every note of the piece whose pitch reaches past the keys the format numbers."""
        return tuple(note for track in self.tracks for note in track.unplayable)

    @property
    def silent_notes(self) -> tuple[NoteEvent, ...]:
        """Every note of the piece reaching a key its track's bank leaves unsampled."""
        return tuple(note for track in self.tracks for note in track.silent)


def build_song(
    arrangement: Arrangement,
    allocation: Allocation,
    grid: RowGrid,
    layout: Layout,
    *,
    target: TrackerTarget,
) -> Conversion:
    """The song a piece becomes: its voices on channels, played through its ensemble, tempo changes and all.

    The piece runs as far as the last release of any of its tracks, and states the clock of the one track
    it keeps time by.
    """
    rows = grid.row_of(arrangement.last_tick) + grid.rows_per_beat * TRAILING_BEATS + 1
    channels = allocation.width
    grids = Grids.covering(
        rows,
        channels=channels,
        height=pattern_height(rows, preferred=layout.height, target=target),
        minimum=target.min_rows,
    )
    sounding = sound(allocation, ensemble=arrangement.ensemble, target=target)
    written = build_patterns(grids, sounding, arrangement.tempos, grid, target=target)
    song = Song(
        name=layout.name,
        channels=channels,
        patterns=written.patterns,
        order=OrderList.sequential(len(written.patterns)),
        voices=arrangement.ensemble.table,
        playback=Playback(
            speed=grid.speed,
            tempo=playable_tempo(
                arrangement.tempos[0].beats_per_minute,
                speed=grid.speed,
                rows_per_beat=grid.rows_per_beat,
                target=target,
            ),
        ),
    )
    return Conversion(
        song=song,
        tracks=report(arrangement, allocation, sounding),
        dropped_tempos=written.dropped_tempos,
    )
