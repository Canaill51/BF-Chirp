# Working on bfchirp

Read [`AGENTS.md`](AGENTS.md) first — it is the canonical brief: commands, the
analysis/rendering rule, the traps that have bitten before, and the conventions.
This file adds only the orientation that saves you re-exploring the codebase.

## Module map

Analysis modules return dataclasses; `report.py` formats. Nothing else formats.

| Module | Role | Imports |
|---|---|---|
| [log.py](src/bfchirp/log.py) | Header parsing, lazy column access, unit conversion, flight mask | — |
| [spectral.py](src/bfchirp/spectral.py) | Welch spectra, band RMS, peak finding, delay fit, phase margin | — |
| [decode.py](src/bfchirp/decode.py) | Locates and runs `blackbox_decode`, one `FlightLog` per segment | `log` |
| [noise.py](src/bfchirp/noise.py) | Raw vs filtered gyro per band, motor harmonics, D-term | `log`, `spectral` |
| [step.py](src/bfchirp/step.py) | Wiener deconvolution of setpoint into gyro | `log` |
| [chirp.py](src/bfchirp/chirp.py) | Sweep segmentation, transfer function, excitation and motor load | `log`, `spectral` |
| [report.py](src/bfchirp/report.py) | Text rendering and `to_jsonable` | result types, `EDGE_HZ` |
| [cli.py](src/bfchirp/cli.py) | Argument parsing, orchestration, exit codes | all of the above |

`log.py` and `spectral.py` are leaves. `report.py` imports the result types
only to render them — if it ever needs to compute, the computation is in the
wrong place.

Two things in `log.py` are worth knowing before touching anything:
`FlightLog` reads only the header at construction and loads columns lazily on
first access, and it registers both spellings of every column name.

## CLI surface

```
bfchirp LOG [LOG ...] [--only noise,step,chirp] [--decoder PATH]
             [--workdir DIR] [--json PATH] [--segment N]
```

`LOG` is a `.bbl`, a `.csv`, or a directory containing them. `--json -` writes
to stdout and suppresses the text report so the two do not interleave.

Exit codes: `2` for a bad request or nothing analysable, `1` if there were
failures *and* nothing was analysed, `0` otherwise.

The chirp analysis is gated on `log.is_chirp` — a property of the data, not of
the request. Asking for `--only chirp` on a plain flight log is not an error;
it reports that there was no sweep. This is why the same command works for
both kinds of log.

## Key constants

| Constant | Module | Meaning |
|---|---|---|
| `EDGE_HZ = 1.5` | `chirp.py` | Nothing below this is trustworthy |
| `EDGE_FRACTION = 0.12` | `chirp.py` | A peak this close to the low edge is an artefact |
| `FLAT_SPAN_DB = 1.0` | `chirp.py` | Peak-to-peak gain below this counts as flat |
| `BAND_EDGES` | `noise.py` | 20/80/200/400/800/1200 Hz; bands past Nyquist are dropped |
| `MIN_EXCITATION_DPS = 20.0` | `step.py` | Below this a window has no usable stick input |
| `WIENER_LAMBDA = 0.02` | `step.py` | Deconvolution regularisation |

`EDGE_HZ` is the one constant shared across the analysis/rendering boundary —
`report.py` imports it to explain the band it is printing.

## Verifying a change

The checklist lives in [AGENTS.md](AGENTS.md#checking-your-work) — tests, then
the upstream drift check, then style, then an honest report. Two practical
notes on top of it:

* `python scripts/fetch_upstream.py` (without `--check`) puts the real firmware
  sources under `vendor/`, so a claim can be read rather than recalled.
  [docs/reference/chirp-firmware.md](docs/reference/chirp-firmware.md) says
  what they mean and which lines matter.
* The drift check needs network. If it cannot run, say so rather than
  presenting a firmware claim as verified — the pin is a statement about a
  specific commit, and an unchecked pin is just a date.
