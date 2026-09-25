# The bank

A **bank** is what the notes of a converted piece play through: one or more sampled instruments, the
rule deciding which of them a note reaches, and the map turning its velocity into the volume column.
Naming a bank is what makes the written module play on its own.

Everything here lives under `midi2tracker/instruments/`.

## Two ways to name one

One instrument covering the whole keyboard is a flag:

```
uv run midi2tracker song.mid song.it --instrument-file Piano/module.it
```

Several instruments, each answering its own notes, is a bank:

```
uv run midi2tracker song.mid song.it --bank Piano.bank
```

Both build the same object. The flag is the bank's single-layer case with its files already named, so a
bank grows from one to many by writing a document rather than by taking another code path.

Naming neither writes one empty slot with a keymap sending every key to it, which is a module to open in
a tracker and drop a waveform into.

An arrangement names one of these per track, in the same words, so a piece assembled from stems plays
each stem through a bank of its own on one instrument table.
[`docs/arrangement.md`](arrangement.md) states that document.

## How a bank is shipped

A bank is a manifest and the instruments it names. Those travel together in either of two packagings, and
`--bank` reads both:

| Named | Read as | Where its entries are |
|---|---|---|
| `Piano.bank` | one archive holding the manifest and every instrument | inside the archive |
| `Piano/bank.json` | a manifest with its instruments beside it | the directory the manifest sits in |

A path ending in `.json` is a manifest read where it sits; anything else is the archive carrying both.
The archive is a zip, so its contents are inspectable with any tool that opens one.

The archive is the form a bank travels in, and the reason is calibration rather than tidiness. A producer
derives what it stores from what it measured — the level a waveform is stored at follows from the
velocity map written for it — so the instruments and the map are one unit that only means anything
together. Shipping them as one file is what stops half of that unit from being copied, renamed or
updated on its own.

Everything above the store reads a bank the same way whichever packaging it was handed, because both
answer one interface: `BankStore.manifest()` and `BankStore.read(name)` in `instruments/store.py`.

## Instrument files

A layer names a file and the position within it, counted from zero. The file's own suffix picks the
reader out of the registry in `instruments/source.py`:

| Suffix | Holds |
|---|---|
| `.it` | An Impulse Tracker module; the instrument at the stated position |
| `.xm` | A FastTracker 2 module; the instrument at the stated position |
| `.iti` | An Impulse Tracker instrument on its own, which is position `0` |
| `.xi` | A FastTracker 2 instrument on its own, which is position `0` |
| `.s3m` | A Scream Tracker 3 module; the sample at the stated position, played as an instrument at the pressed key's pitch |
| `.mod` | A ProTracker module; the sample at the stated position, played as an instrument at the pressed key's pitch |

A **standalone instrument file** is what a producer ships when the instrument rather than a piece is the
product, and a module carrying one instrument is the other way to ship exactly the same thing. Both are
one reference — a file and a position within it — so a layer names either the same way and a manifest
reads the same whichever it points at. `trackmod` binds all six, so the reader is chosen and nothing
else about a bank changes.

A file holding one instrument holds one, so naming a position above `0` in it is reported the way naming
a position past the end of a module is.

### What each container keeps

An Impulse Tracker keymap stores a sample number per key and reserves zero for silence. A FastTracker 2
keymap stores a sample position per key, and `trackmod` writes a key meant to stay silent as a position
past the instrument's stored samples, which reads back as silence. Every container `trackmod` writes
therefore carries the stretch a producer sampled exactly as it was recorded. A FastTracker 2 container
written by another tracker routes **every one of the 96 keys the format stores** to a sample, so each
unsampled key there sounds whichever sample that tracker placed on it.

What a bank reads is independent of what a conversion writes — an Impulse Tracker instrument is equally
available to a module written as FastTracker 2, and the crossing is graded by the writer (see
[Producing for the format the module is written as](#producing-for-the-format-the-module-is-written-as)).

An instrument is taken **verbatim**: its keymap, every sample's PCM, rate, depth, volume, gain, panning
and loops, and its envelopes, fadeout and note behaviours all reach the written module as they were
produced. A conversion states notes; the articulation belongs to whoever sampled the instrument. What
surrounds the instrument in the file it came out of — the module's patterns, its clock, the instruments
at other positions — stays where it is.

## The manifest

JSON, stored as the bank's `bank.json`, naming each instrument as an entry of the bank it belongs to:

```json
{
  "version": 2,
  "name": "Piano",
  "tempo": 125,
  "layers": [
    {
      "source": {"file": "instruments/quiet.iti", "instrument": 0},
      "select": {"velocity": {"low": 0, "high": 63}},
      "velocity_map": {"volumes": [2, 2, 3, "…", 64]}
    },
    {
      "source": {"file": "instruments/loud.iti"},
      "velocity_map": {"volumes": [4, 5, 5, "…", 64]}
    }
  ]
}
```

An entry name is read against the bank rather than against a directory, so one document describes the
archive and the loose directory alike: inside an archive it names an entry, and beside a manifest it
names a file in that directory.

Every field is read, and this is what each one decides:

| Field | What it decides |
|---|---|
| `version` | The shape this document is written in; a manifest stating another version is refused |
| `name` | What the bank is called; a run prints it, so a summary says what the piece played through |
| `tempo` | The clock this bank's volume envelopes were fitted against; omit it for a bank assembled by hand |
| `layers` | The instruments, in the order they are tried; at least one |
| `layers[].source.file` | The entry of the bank the instrument is read out of |
| `layers[].source.instrument` | Which instrument of that entry, counted from zero; `0` when omitted, which is what a standalone instrument file holds |
| `layers[].select` | Which notes this layer answers; omitting it answers every note |
| `layers[].velocity_map` | The table this layer's velocities were measured as, stated inline; omitting it reads them evenly |

Fields outside this shape are ignored, so a manifest written by a later producer still loads and
contributes what it shares — the same rule `Config.load` follows for the settings file.

`tempo` is the one field describing the bank as a whole rather than one of its layers. A format counts
envelope breakpoints in ticks, so a curve plays the shape it was fitted with at the tempo it was fitted
at. A written module carries a clock of its own; an instrument lifted out of one into a bank states that
clock here instead. A piece played at this tempo hears every envelope over the stretch of time its
producer shaped it for, and a piece played twice as fast hears the same curve over half of it.

It records a measurement, so a bank assembled by hand out of loose instrument files leaves it open, the
way such a layer leaves its `velocity_map` open. An [arrangement](arrangement.md) writing its `layers`
inline is that case.

### Which layer a note reaches

`select` maps an **axis name** to a band with both ends counted as inside it. A note's coordinates along
the axes are its `Expression`, read from what the MIDI file states about the note:

| Axis | Reads | The bands it is for |
|---|---|---|
| `velocity` | `NoteEvent.velocity` | The dynamic layers a producer sampled and measured apart from each other |
| `pitch` | `NoteEvent.pitch`, in MIDI numbering | The instruments a producer wrote one layer's keyboard across |

Layers are tried in order, and the first whose every stated band covers the note answers it. An axis a
layer leaves out answers the whole of it, so a bank reads from its most particular case down to its most
general — the manifest above sends velocities 0..63 to the quiet instrument and everything else to the
loud one.

Each layer becomes one instrument slot in the written module, in manifest order.

A layer answering a note still leaves it silent when the layer's own keymap routes that key nowhere,
which is the ordinary case of a sampled instrument covering the stretch of keyboard it was recorded
over. The run [reports those notes](#what-a-run-reports).

### Why the pitch is an axis of its own

A keymap already says which sample a key reaches, so where one instrument holds a whole layer the pitch
decides nothing a bank has to state. It carries weight where a **format numbers few samples inside one
instrument** — FastTracker 2 reads sixteen — and a producer therefore writes one layer's keyboard across
several instruments. Each of those is a standalone file that answers every key it was filled over, so two
of them offered the same key both say yes, and the pitch band is what says which of them owns that
stretch:

```json
"layers": [
  {"source": {"file": "instruments/p029-p060_v000-v127.xi"},
   "select": {"pitch": {"low": 0, "high": 60}}},
  {"source": {"file": "instruments/p061-p101_v000-v127.xi"},
   "select": {"pitch": {"low": 61, "high": 127}}}
]
```

The bands tile the whole axis rather than stopping at the keys each file was recorded over, so a note
outside the sampled stretch reaches the nearest instrument and sounds whatever that instrument's keymap
was filled with — the same thing a bank of one instrument does with it.

### Adding an axis

A third axis is a member of `Axis`, a field on `Expression`, and an arm in its reader. The document shape
holds still, because a selector names its axes by those very strings.

Velocity and pitch both read fields the parser already keeps on `NoteEvent`. An axis over controllers
needs `midi/parser.py` to retain their values, which today it reads for the sustain pedal.

## Velocity maps

A velocity map states the volume column each of the 128 MIDI velocities sounds at, on the tracker's own
`0..64` scale:

```json
{
  "reference_volume": 64,
  "anchors": [{"velocity": 3, "loudness_lufs": -52.31, "volume": 2}],
  "volumes": [2, 2, 3, "…", 64]
}
```

`volumes` is what is read — exactly 128 entries, each in `0..64`, one per MIDI velocity. The rest of the
document is the measurement it was derived from: `anchors` records the loudness a producer measured at
the velocities it rendered, and `reference_volume` the level those measurements were taken against. The
table already states the conclusion, so reading it alone lets the same content both drive a conversion
and document how its numbers were arrived at.

The map belongs to a layer rather than to the bank, because each layer's samples were measured against
their own. Inside a bank it is stated inline, in the layer that was measured with it. A layer stating no
map reads velocity evenly, `round(velocity * 64 / 127)`, which is the right reading where a waveform's
own level already stands for the velocity it was recorded at.

`--instrument-file` names one instrument, and `--velocity-map` names the map it is read with, as the same
document above written to a file of its own. Naming an instrument alone reads velocity evenly. Every file
a run reads is a file it was pointed at, so what a conversion plays follows from its settings rather than
from what happens to sit beside a path.

A measured map records loudness, so its numbers rise and fall as the recordings do: velocities 50, 60,
70, 75, 80, 90 and 100 of the verified `Piano` sound at 7, 20, 13, 26, 26, 25 and 21. Those are the
numbers written into the volume column, dips and all.

## Where the instruments sit

`--instrument` (`instrument:` in the settings file) is the slot the bank's layers start on. The slots
below it are numbered and hold an instrument routing no key to a sample, so a module can reserve the
positions a tracker convention expects and still say exactly which of them the piece plays.

Impulse Tracker numbers 99 instrument slots and FastTracker 2 numbers 128, and `--compliance extended`
raises both to 255, so the offset plus the layer count is graded against the format and compliance the
module is written as.

## What a run reports

A real instrument makes two kinds of silence audible that an empty slot never could, so `--verbose`
names the pitches behind each:

```
  note          3 note(s) reach a key the bank leaves unsampled
  left unsampled by the bank
    MIDI 20, 110, 127
```

A layer's keymap routes the keys it was sampled over, and a note reaching any other key sounds nothing.
That covers both the keys past either end of the instrument's stretch and the ones inside it a producer
spent its byte budget elsewhere than on — the verified `Piano` runs from MIDI 29 to 101 and routes 61 of
those 73 keys. Sampling more widely, or more densely, is the fix.

```
  note          2 note(s) lie past the keys this format numbers
  past the keys this format numbers
    MIDI 110, 127
```

Impulse Tracker numbers MIDI 12..131 and FastTracker 2 stops at 107, so a note above one format's
keyboard is a note the other states. Writing the piece as `.it` is the fix.

The two are counted apart because their fixes differ. Both leave the note out and name its pitch, so the
piece sounds the notes the MIDI file states and the summary accounts for the rest.

## Producing for the format the module is written as

An Impulse Tracker instrument written into a FastTracker 2 module is refused, and the refusal is
correct. FastTracker 2 has no per-sample gain field, so a bank staged with one reports a **structural**
violation for every sample it holds quieter than full:

```
$ uv run midi2tracker song.mid out.xm --format xm --instrument-file Piano/module.it
cannot write this module:
  sample 0 ('Piano F1'): sample_gain is 24, outside 64..64 (structural)
  …
  instrument 0 ('Piano'): samples_per_instrument is 61, outside 0..16 (canonical)
```

Sixty of the `Piano`'s sixty-one samples are staged below full gain, and the count of samples one
instrument reaches is bounded separately: 61 against the 16 FastTracker 2 itself reads, which
`--compliance extended` lifts. The gain violations hold at every compliance level, because the field the
value would be written into is absent from the format.

The fix is to produce the bank for the format it will be played in: OptiSample's `format: xm` carries the
level balance in the waveforms themselves, where a producer holding the full-resolution recording can
apply it once. A written module states the instrument it was given and reports what the format declines
to hold, which keeps the gain staging in the hands that measured it.

Impulse Tracker is the default output for the same reason it is the better home for a layered bank: it
stores one flat sample table the keymaps index into, where FastTracker 2 gives every instrument its own
copies, so a waveform two layers share costs one slot there and two in an `.xm`.

## Producing a bank

[OptiSample](https://github.com/JakimPL/OptiSample) writes exactly what this reads. One of its
instrument directories holds

```
Piano.bank           the manifest, the instruments it names and the velocities they were measured at
instruments/         each written instrument on its own, named by the keys and dynamics it answers
```

`--bank Piano.bank` takes the bank whole, and `--instrument-file instruments/<one>.iti` takes a single
voice out of it — with `--velocity-map` where that voice was measured. A producer chooses the container
and the flag stays one flag. The verified `Piano` routes
61 keys between MIDI 29 and 101 onto 61 samples, recorded at 6–16 kHz in eight and sixteen bits, each
staged with its own gain — 524 KB of module that plays with no tracker opened.

A byte budget is what a producer spends, so the instrument it settles on is the one that fits: the
`Piano` keeps 61 of the 73 keys in its stretch and leaves the other twelve to be reported, and its
samples run 0.04–2.42 seconds with six of them looped, so a note held past its sample's end sounds for
as long as the recording lasts. Both are the producer's decisions, and a conversion states them as they
were made.

The manifest is what names the files under `instruments/` as one instrument, whether they are the layers
of a velocity split, the stretches of keyboard a format's sample bound cut one layer into, or both.

## Checking a bank end to end

A converted module renders without a tracker:

```
uv run midi2tracker song.mid piano.it --instrument-file Piano/module.it --verbose
openmpt123 --render piano.it        # writes piano.it.wav
```

Two probes say whether what came out is what was asked for, and both hold for the verified `Piano`:

- **Pitch.** One note per octave, struck a second apart. Reading the strongest partial at each onset off
  an FFT puts MIDI 41 through 101 within 20 cents of equal temperament, the deviation growing with pitch
  as the recording's own resampling and the integer sample rate a module stores account for.
- **Dynamics.** One pitch struck at rising velocities. The rendered peak tracks the map's volume column
  exactly — `r = 1.0000` against the `Piano`'s table, including the places where a higher velocity is
  the quieter one, which is the measurement reaching the audio.

A held note sounds for as long as its sample lasts, so a piece rendered against a byte-budgeted
instrument goes quiet under long chords. The sample lengths in the source instrument say how long that
is.
