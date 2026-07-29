# The arrangement

An **arrangement** is several MIDI files converted into one module: each file becomes a track, each track
plays through a bank of its own, and the tracks share one instrument table and one channel table.

```
uv run midi2tracker song.yaml song.it --verbose
```

A `.yaml` or `.yml` input is read as the document below; anything else is one MIDI file, which is the
single-track arrangement the settings already describe. Both reach the same object, so everything the
conversion does downstream reads one shape.

Everything here lives under `midi2tracker/arrangement/`.

## The document

```yaml
# song.yaml — every path is read against this file's own directory
name: Nocturne             # what the module calls itself; omit for the document's file name
clock: brass.mid           # the track whose tempo map the piece follows; omit for the first
allocation: separated      # how the tracks share the channel table; omit for the setting

tracks:
  bass.mid: Bass/Bass.bank             # a path alone names the bank the track plays through

  brass.mid:                           # the loose pair, exactly as the flags state it
    instrument_file: Brass/Brass.iti
    velocity_map: Brass/map.json
    channels: 8                        # this track's own ceiling

  woodwinds.mid:                       # a bank written where it is used
    name: Woodwinds
    layers:
      - source: {file: Wood/soft.iti}
        select: {velocity: {low: 0, high: 63}}
      - source: {file: Wood/loud.iti}

  drums.mid:                           # naming nothing plays the slot a tracker fills in by hand
```

`tracks` states at least one file, and the order it states them in is the order the module lays them out.

Each value names its instruments the way the settings name them for a single piece — a `bank`, an
`instrument_file` with the `velocity_map` it was measured against, or the `layers` a bank is made of
written inline — and one track states one of those. [`docs/bank.md`](bank.md) covers what each holds.

| Key | What it decides |
|---|---|
| `bank` | a container, or a manifest, naming the instruments this track's notes play through |
| `instrument_file` | one instrument file every note of this track plays through |
| `velocity_map` | the velocity map that file is read with; omit to read velocity evenly |
| `layers` | the layers a bank is made of, stated here rather than shipped as a file |
| `name` | what the track is called in the summary, and what an inline bank calls itself |
| `channels` | this track's own ceiling; omit to be held to the `channels` setting |

Two tracks naming the same instruments are handed the same bank, so a piece assembled from stems of one
instrument costs that instrument one set of slots and stores its samples once.

Keys outside this shape are ignored, so a document written for a later version still loads and
contributes what it shares.

## One tick scale

The files an arrangement names were written at whatever resolution each was written at. Every track is
put on the least common multiple of those resolutions, which is a whole multiple of each, so every event
lands on the beat its own file put it on and combining the tracks costs no rounding.

## One clock

A module keeps one clock. `clock` names the track whose tempo map the piece plays; omitting it follows the
first track the document states. `--tempo` replaces the opening BPM of that track, since that map is the
one the module carries.

A tempo another track states is read for its notes alone, and `--verbose` names each one — the track, the
tick and the BPM — so a piece following the wrong stem's timing says which stem to point `clock` at.

## How the tracks share the channels

`allocation` decides what the tracks make of the channel table. Each track allocates within its own
ceiling either way: a track at its ceiling gives up its own oldest voice rather than reaching for a
channel another track holds, so a ceiling means the same thing in both.

| `allocation` | What the tracks do | The module comes out |
|---|---|---|
| `separated` | each track takes a run of channels of its own | as wide as the tracks reach together |
| `packed` | every track draws from one pool | as wide as the piece ever sounds at once |

`separated` is the default, and it is what makes a module read as the stems it was assembled from — one
part per run of channels, which is what an editor shows and a mixer expects. `packed` fills the gaps in
each track's polyphony with another track's notes, which is what a piece wider than the format plays
needs.

A document stating `allocation` keeps that layout wherever it is converted from, so `--allocation`
supplies what a document leaves out rather than overriding what it states.

The width follows from the piece — its polyphony, each track's ceiling, and the way the tracks share —
so it is derived rather than set, and rounded up to a stereo pair. A width past what the format plays is
refused before anything is written, naming what each track contributed and how wide the other way of
sharing would reach:

```
cannot lay this piece out:
  separated allocation reaches 36 channels, where XM plays 32: bass 12, brass 12, woodwinds 12;
  packed allocation reaches 12
```

## What a run reports

The summary states the whole piece and then each track of it, since each loss is corrected in one track
at a time — a ceiling raised on one part, one instrument sampled more widely, one part transposed:

```
song.it
  file size     1,204,880 bytes
  patterns      22  (1382 rows)
  channels      16
  notes         1020
  tracks        4  (separated)
    bass        2 channel(s)   140 note(s)
    brass       8 channel(s)   593 note(s)  (24 displaced)
    woodwinds   2 channel(s)   215 note(s)  (3 unsampled)
    drums       4 channel(s)    72 note(s)
  bank          Bass, Brass, Woodwinds, Placeholder
  instruments   5  (9 sample(s))
  ...
```

A piece read from one MIDI file states its channels and its losses in the lines around that block
already, so it prints no track breakdown.
