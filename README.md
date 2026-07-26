# midi2xm

Convert a MIDI file into a FastTracker 2 tracker module.

```
uv run midi2xm song.mid
```

writes `song.xm` beside it: the sustain pedal resolved, the notes spread over as many channels as the
polyphony needs, and the tempo changes carried through as effects.

The module comes out with one **empty instrument slot** and a keymap sending every key to it. Open the
file in a tracker, drop a waveform into that slot, and the piece plays — the volume envelope holds while a
key is down and falls silent when it is released, so a real sample lasts exactly as long as the grid says.

## What it does with a MIDI file

| MIDI | Module |
|---|---|
| a note | a cell that names the key, the instrument and the velocity as a volume |
| a note released later | a key-off on the row it releases on |
| a note starting between rows | a note-delay effect carrying the remainder |
| the sustain pedal (CC 64) | a note that keeps sounding until the pedal lifts |
| a tempo change | a tempo effect on the lowest channel with a free effect column |
| more notes at once than there are channels | the oldest voice gives up its channel, and the count is reported |

## Options

Every knob has a flag and a `config.yaml` entry; the file supplies the defaults the flags override.

| Setting | What it decides |
|---|---|
| `rows_per_beat` | how many rows a quarter note is spread over — the grid's resolution |
| `channels` | the polyphony ceiling |
| `pattern_rows` | how tall one pattern may be; raised automatically when a piece needs fewer patterns than the order table names |
| `speed` | ticks per row; `0` chooses the finest the piece's fastest tempo allows |
| `tempo` | an opening BPM override; omit to read it from the file |
| `instrument` | which instrument slot the notes play through |

```
uv run midi2xm song.mid out.xm --rows-per-beat 8 --channels 16 --verbose
```

## How it is put together

Everything about the *file format* lives in [`trackmod`](../AudioTokenizer/docs/trackmod/overview.md),
which holds one format-agnostic song model and writes it as `.xm`. What is here is the MIDI side and the
translation between them.

| Package | Owns |
|---|---|
| `midi2xm/midi` | reading a file down to notes and tempos, with the sustain pedal resolved |
| `midi2xm/timing` | the tick-to-row grid, the speed choice, and the tempo conversion |
| `midi2xm/voices` | spreading overlapping notes across channels |
| `midi2xm/song` | writing those voices onto pattern grids and assembling the song |
| `midi2xm/convert.py` | one file to one module, end to end |
| `midi2xm/cli.py` | the command line |

Two ceilings shape most of the decisions, and both come from the format rather than from taste: a tempo
effect's parameter is one byte, and a note delay is one nibble — so a row divided into more than sixteen
ticks would have positions no cell could name.

## Development

```
make format   # isort + black
make lint     # mypy --strict + pylint
make test     # pytest
```
