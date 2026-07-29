# midi2tracker

Convert a MIDI file, or an arrangement of several, into an Impulse Tracker or FastTracker 2 module.

## Getting started

The file format lives in [`trackmod`](https://github.com/JakimPL/TrackMod), taken here as a git submodule
so a checkout pins the exact revision this project was built against. Fetch it before anything else — an
empty `trackmod/` leaves the project uninstallable:

```
git submodule update --init
uv sync
```

A fresh clone can do both in one step with `git clone --recurse-submodules`.

```
uv run midi2tracker song.mid song.it
```

writes `song.it`: the sustain pedal resolved, the notes spread over as many channels as the polyphony
needs, and the tempo changes carried through as effects. `--format xm` writes the same piece as `.xm`
instead, and each format states it in its own terms.

Point it at a sampled instrument and the module plays on its own:

```
uv run midi2tracker song.mid song.it --instrument-file Piano/module.it
```

The instrument is carried over as it was produced — its keymap, samples, gains and envelopes all as
stated — and `--velocity-map` names the table it was measured with, so each velocity sounds at the volume
it was measured at. A whole module and a standalone instrument (`.it`, `.xm`, `.iti`, `.xi`) are read the
same way, so the flag takes whichever container a producer ships.

`--bank` takes several instruments at once, and the notes each one answers, as a **bank**: one file
holding the manifest, the instruments and the velocities they were measured at.
[`OptiSample`](https://github.com/JakimPL/OptiSample) writes one; a bank spread over a directory beside
its `bank.json` is read the same way. [`docs/bank.md`](docs/bank.md) states both in full.

Naming no instrument writes one **empty slot** with a keymap sending every key to it. Open the file in a
tracker, drop a waveform into that slot, and the piece plays — the volume envelope holds while a key is
down and falls silent when it is released, so a real sample lasts exactly as long as the grid says.

A `.yaml` input is an **arrangement**: several MIDI files as one module, each track playing through a
bank of its own, on one instrument table and one channel table.

```yaml
# song.yaml
tracks:
  bass.mid: Bass/Bass.bank
  brass.mid:
    instrument_file: Brass/Brass.iti
    channels: 8
```

```
uv run midi2tracker song.yaml song.it
```

`allocation` decides what the tracks make of the channel table: `separated` gives each one a run of
channels of its own, so the module reads as the stems it was assembled from, and `packed` draws every
track from one pool, so the piece spans the channels it sounds at once rather than the channels it sounds
altogether. [`docs/arrangement.md`](docs/arrangement.md) states the document in full.

## What it does with a MIDI file

| MIDI | Module |
|---|---|
| a note | a cell that names the key, the instrument and the velocity as a volume |
| a note released later | a key-off on the row it releases on |
| a note starting between rows | a note-delay effect carrying the remainder |
| the sustain pedal (CC 64) | a note that keeps sounding until the pedal lifts |
| a tempo change | a tempo effect on the lowest channel with a free effect column |
| more notes at once than a track has channels | that track's oldest voice gives up its channel, and the count is reported |
| a tempo change on a track the piece keeps no time by | read for its notes, and the tempo named in the summary |
| a note past the keys the format numbers | left out, and its pitch named in the summary |
| a note on a key the bank never sampled | left out, and its pitch named in the summary |

## Options

Every knob has a flag and a `config.yaml` entry; the file supplies the defaults the flags override.

| Setting | What it decides |
|---|---|
| `format` | the tracker format the module is written as: `it` or `xm` |
| `compliance` | `canonical` holds to what the tracker the format was designed for reads; `extended` to what the file layout holds |
| `rows_per_beat` | how many rows a quarter note is spread over — the grid's resolution |
| `channels` | how many channels one track's polyphony may reach; an arrangement states it per track |
| `allocation` | how the tracks of an arrangement share the channel table: `separated` or `packed` |
| `pattern_rows` | how tall one pattern may be; raised automatically when a piece needs fewer patterns than the order table names, or when the format states a taller floor |
| `speed` | ticks per row; `0` chooses the finest the piece's fastest tempo allows |
| `tempo` | an opening BPM override; omit to read it from the file |
| `instrument` | which slot the instruments start on |
| `bank` | a bank — a container, or a manifest — naming the instruments the notes play through, and which notes reach each one |
| `instrument_file` | one instrument file every note plays through, instead of a bank |
| `velocity_map` | the velocity map that file is read with; omit to read velocity evenly |

Every count is graded against the format it is written for, because the two bound them differently:
Impulse Tracker plays 64 channels of 200-row patterns and reaches all ten octaves, where FastTracker 2
plays 32 of 256 and stops eight octaves up. A number one format carries and the other refuses is
reported where it is given.

```
uv run midi2tracker song.mid out.xm --format xm --rows-per-beat 8 --channels 16 --verbose
```

## How it is put together

Everything about the *file formats* lives in
[`trackmod`](https://github.com/JakimPL/TrackMod/blob/main/docs/overview.md), which holds one
format-agnostic song model and binds it to `.it` and `.xm`. What is here is the MIDI side and the
translation between them.

| Package | Owns |
|---|---|
| `midi2tracker/midi` | reading a file down to notes and tempos, with the sustain pedal resolved |
| `midi2tracker/arrangement` | several MIDI files as one piece: what each plays through, and the clock they follow |
| `midi2tracker/timing` | the tick-to-row grid, the speed choice, and the tempo conversion |
| `midi2tracker/voices` | spreading overlapping notes across channels |
| `midi2tracker/song` | writing those voices onto pattern grids and assembling the song |
| `midi2tracker/instruments` | the bank: which instrument a note plays through, and at what volume |
| `midi2tracker/tracker` | the one place that branches on the format: every bound, effect and key comes from here |
| `midi2tracker/convert.py` | one piece to one module, end to end |
| `midi2tracker/cli.py` | the command line |

Every pass states what it needs in terms both formats share and asks a `TrackerTarget` for the numbers,
so adding a format means adding its arms there. Two ceilings shape most of the decisions, and both come
from the format rather than from taste: a tempo effect's parameter is one byte, and a note delay is one
nibble — so a row divided into more than sixteen ticks would have positions no cell could name.

[`docs/bank.md`](docs/bank.md) covers the instrument side: the manifest, the velocity map, which slot
each layer lands on, and which format a bank belongs to. [`docs/arrangement.md`](docs/arrangement.md)
covers the piece side: the document, the clock the tracks follow, and the two ways they share the
channel table.

## Development

```
make format   # isort + black
make lint     # mypy --strict + pylint
make test     # pytest
```
