from dataclasses import dataclass

from trackmod.core.effects.catalog import EffectCatalog
from trackmod.core.notes.pitch import Note
from trackmod.core.songs.song import Song
from trackmod.limits.bound import Bound
from trackmod.limits.capability import Capability
from trackmod.limits.compliance import Compliance
from trackmod.limits.table import Limits
from trackmod.module.protocol import TrackerModule
from trackmod.spec.pitch import MIDI_OFFSET
from trackmod.trackers.it.effects.catalog import IT_EFFECTS
from trackmod.trackers.it.limits import it_limits
from trackmod.trackers.it.module import ITModule
from trackmod.trackers.it.settings import ITSettings
from trackmod.trackers.it.spec.effects import NIBBLE_PARAMETER as IT_NIBBLE_PARAMETER
from trackmod.trackers.it.spec.effects import SPEED_PARAMETER as IT_SPEED_PARAMETER
from trackmod.trackers.it.spec.effects import TEMPO_PARAMETER as IT_TEMPO_PARAMETER
from trackmod.trackers.it.spec.identity import EXTENSION as IT_EXTENSION
from trackmod.trackers.xm.effects.catalog import XM_EFFECTS
from trackmod.trackers.xm.limits import xm_limits
from trackmod.trackers.xm.module import XMModule
from trackmod.trackers.xm.settings import XMSettings
from trackmod.trackers.xm.spec.effects import NIBBLE_PARAMETER as XM_NIBBLE_PARAMETER
from trackmod.trackers.xm.spec.effects import SPEED_PARAMETER as XM_SPEED_PARAMETER
from trackmod.trackers.xm.spec.effects import TEMPO_PARAMETER as XM_TEMPO_PARAMETER
from trackmod.trackers.xm.spec.identity import EXTENSION as XM_EXTENSION

from midi2tracker.tracker.format import TrackerFormat
from midi2tracker.tracker.settings import IT_SETTINGS, XM_SETTINGS


@dataclass(frozen=True)
class TrackerTarget:
    """The format a conversion is written as, together with everything that format decides.

    Every pass that lays out a song asks its bounds here, so the passes state what they need in terms
    both formats share and this one place answers it per format. Adding a format means adding its arms
    to the members that branch and letting the rest read the capacity table.

    ``compliance`` picks which bounds a module is graded against, and it reaches the layout too: the
    canonical Impulse Tracker floor is 32 rows a pattern, so material cut under it is padded up to that
    height.
    """

    format: TrackerFormat
    compliance: Compliance
    it: ITSettings = IT_SETTINGS
    xm: XMSettings = XM_SETTINGS

    def bind(self, song: Song) -> TrackerModule:
        """Hand ``song`` to this format, giving a module that reports its size and writes itself."""
        match self.format:
            case TrackerFormat.IT:
                return ITModule.from_song(song, compliance=self.compliance, settings=self.it)
            case TrackerFormat.XM:
                return XMModule.from_song(song, compliance=self.compliance, settings=self.xm)

    @property
    def extension(self) -> str:
        """The file extension a module of this format is written with, including the leading dot."""
        match self.format:
            case TrackerFormat.IT:
                return IT_EXTENSION
            case TrackerFormat.XM:
                return XM_EXTENSION

    @property
    def limits(self) -> Limits:
        """The bounds a module of this format is held to at this compliance level."""
        match self.format:
            case TrackerFormat.IT:
                return it_limits(self.compliance)
            case TrackerFormat.XM:
                return xm_limits(self.compliance)

    @property
    def effects(self) -> EffectCatalog:
        """The shared effect vocabulary as this format spells it."""
        match self.format:
            case TrackerFormat.IT:
                return IT_EFFECTS
            case TrackerFormat.XM:
                return XM_EFFECTS

    @property
    def speed_parameter(self) -> Bound:
        """What the parameter of the speed effect names."""
        match self.format:
            case TrackerFormat.IT:
                return IT_SPEED_PARAMETER
            case TrackerFormat.XM:
                return XM_SPEED_PARAMETER

    @property
    def tempo_parameter(self) -> Bound:
        """What the parameter of the tempo effect names."""
        match self.format:
            case TrackerFormat.IT:
                return IT_TEMPO_PARAMETER
            case TrackerFormat.XM:
                return XM_TEMPO_PARAMETER

    @property
    def nibble_parameter(self) -> Bound:
        """What one nibble of an effect parameter names, which is the room a note delay has."""
        match self.format:
            case TrackerFormat.IT:
                return IT_NIBBLE_PARAMETER
            case TrackerFormat.XM:
                return XM_NIBBLE_PARAMETER

    @property
    def max_patterns(self) -> int:
        """How many patterns a module of this format holds."""
        return self.limits.bound(Capability.PATTERNS).maximum

    @property
    def min_rows(self) -> int:
        """The shortest pattern this format accepts, which laid-out material is padded up to."""
        return self.limits.bound(Capability.PATTERN_ROWS).minimum

    @property
    def max_rows(self) -> int:
        """The tallest pattern this format accepts, past which material spills into the next one."""
        return self.limits.bound(Capability.PATTERN_ROWS).maximum

    @property
    def max_channels(self) -> int:
        """How wide a module of this format plays."""
        return self.limits.bound(Capability.CHANNELS).maximum

    @property
    def max_instruments(self) -> int:
        """How many instrument slots a module of this format names."""
        return self.limits.bound(Capability.INSTRUMENTS).maximum

    @property
    def keys(self) -> Bound:
        """The keys this format's note column numbers, counted in semitones above C-0."""
        return self.limits.bound(Capability.NOTE)

    def carries(self, pitch: int) -> bool:
        """Whether this format's keyboard reaches a MIDI pitch.

        Trackers count their keyboards from C-0, one octave below MIDI's own numbering, and each format
        numbers a different stretch of it — Impulse Tracker all ten octaves, FastTracker 2 the lowest
        eight — so which pitches a module states is the target's to answer.
        """
        return self.keys.contains(pitch - MIDI_OFFSET)

    def key(self, pitch: int) -> Note:
        """The key this format plays a MIDI pitch on, in the octave the pitch was written in.

        Raises:
            ValueError: when this format's keyboard stops short of the pitch, which :meth:`carries`
                reports beforehand so a piece states the notes it reaches and names the rest.
        """
        if not self.carries(pitch):
            raise ValueError(f"{self.format.upper()} numbers no key for MIDI pitch {pitch}")

        return Note(pitch - MIDI_OFFSET)
