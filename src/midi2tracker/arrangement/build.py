from __future__ import annotations

import math
from pathlib import Path

from midi2tracker.arrangement.document import ArrangementDocument, arranges
from midi2tracker.arrangement.error import ArrangementError
from midi2tracker.arrangement.piece import Arrangement
from midi2tracker.arrangement.spec import TrackSpec
from midi2tracker.arrangement.track import Track
from midi2tracker.config import Config
from midi2tracker.instruments.bank import Bank
from midi2tracker.instruments.ensemble import Ensemble
from midi2tracker.instruments.manifest import MANIFEST_VERSION, BankManifest
from midi2tracker.instruments.store import StatedStore, open_bank
from midi2tracker.midi.events import MidiSong
from midi2tracker.midi.parser import parse_midi

HERE = Path()


def _read(path: Path) -> MidiSong:
    """One MIDI file of an arrangement, read as the notes and tempos it plays.

    Raises:
        ArrangementError: when the file cannot be read as MIDI.
    """
    try:
        return parse_midi(path)
    except (OSError, ValueError, EOFError, IndexError) as unreadable:
        raise ArrangementError(f"{path} does not read as a MIDI file: {unreadable}") from unreadable


def _bank(spec: TrackSpec, *, root: Path, name: str) -> Bank:
    """The instruments one track plays through, from whichever of its fields names them.

    Raises:
        BankError: when the bank, an instrument, or a velocity map cannot be read.
    """
    if spec.bank is not None:
        return Bank.from_store(open_bank(root / spec.bank))

    if spec.layers is not None:
        stated = BankManifest(version=MANIFEST_VERSION, name=spec.name or name, layers=spec.layers)
        return Bank.from_store(StatedStore(stated=stated, root=root))

    if spec.instrument_file is not None:
        measured = None if spec.velocity_map is None else root / spec.velocity_map
        return Bank.from_instrument(root / spec.instrument_file, velocity_map=measured)

    return Bank.placeholder()


def _banked(document: ArrangementDocument, root: Path) -> tuple[Bank, ...]:
    """One bank per track, with tracks naming the same instruments handed the very same bank.

    Sharing the object is what lets the ensemble place those tracks on one set of slots, so a piece
    assembled from stems of one instrument costs that instrument once.
    """
    shared: dict[str, Bank] = {}
    banks: list[Bank] = []
    for path, spec in document.tracks.items():
        key = spec.instruments
        if key not in shared:
            shared[key] = _bank(spec, root=root, name=spec.name or path.stem)

        banks.append(shared[key])

    return tuple(banks)


def _on_one_scale(songs: tuple[MidiSong, ...]) -> tuple[MidiSong, ...]:
    """Every song counted in the finest resolution that states all of them exactly.

    The least common multiple of the files' own resolutions is a whole multiple of each, so every event
    lands on the beat its own file put it on and combining the tracks costs no rounding.
    """
    common = math.lcm(*(song.pulses_per_beat for song in songs))
    return tuple(song.rescaled(common) for song in songs)


def build(document: ArrangementDocument, *, root: Path, config: Config) -> Arrangement:
    """The piece a document describes: every file read, on one tick scale and one clock.

    ``root`` is the directory the document's paths are read against. The timekeeping track's opening
    tempo is what a stated override replaces, since that map is the one the module plays.

    Raises:
        ArrangementError: when a MIDI file the document names cannot be read.
        BankError: when a bank, an instrument, or a velocity map cannot be read.
    """
    specs = tuple(document.tracks.values())
    paths = tuple(document.tracks)
    songs = _on_one_scale(tuple(_read(root / path) for path in paths))
    banks = _banked(document, root)

    timekeeper = document.timekeeper
    if config.tempo is not None:
        songs = tuple(
            song.starting_at(config.tempo) if index == timekeeper else song for index, song in enumerate(songs)
        )

    tracks = tuple(
        Track(
            name=spec.name or path.stem,
            midi=song,
            bank=bank,
            channels=config.channels if spec.channels is None else spec.channels,
        )
        for path, spec, song, bank in zip(paths, specs, songs, banks, strict=True)
    )
    return Arrangement(
        name=document.name or paths[0].stem,
        tracks=tracks,
        ensemble=Ensemble.of(banks, reserved=config.slot),
        timekeeper=timekeeper,
        allocation=document.allocation or config.allocation,
    )


def arrange(source: Path, config: Config) -> Arrangement:
    """The piece ``source`` names, whether it is a whole arrangement or one MIDI file.

    A ``.yaml`` or ``.yml`` source is the document, with its paths read against the directory it sits in.
    Anything else is one MIDI file, which is the single-track arrangement the settings already describe —
    so both reach the same object and everything downstream reads one shape.

    Raises:
        ArrangementError: when the arrangement, or a MIDI file it names, cannot be read.
        BankError: when a bank, an instrument, or a velocity map cannot be read.
    """
    if arranges(source.suffix):
        return build(ArrangementDocument.load(source), root=source.parent, config=config)

    document = ArrangementDocument.of(
        source,
        bank=config.bank,
        instrument_file=config.instrument_file,
        velocity_map=config.velocity_map,
    )
    return build(document, root=HERE, config=config)
