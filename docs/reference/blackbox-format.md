# The blackbox log format

`bfchirp` never parses a binary `.bbl` itself — it shells out to
`blackbox_decode` and reads the CSV. This page covers what the format implies
for the CSV that comes out the other end, which is the part that affects
analysis.

## File structure

A log is a header of ASCII lines followed by a payload of binary frames. Each
header line is `H fieldname:value\n`; the header ends at the first line not
starting with `H`. The start marker is:

```
H Product:Blackbox flight data recorder by Nicholas Sherlock
```

which lets a decoder find a log embedded in a larger file. A single `.bbl` can
hold several logs concatenated — one per arm/disarm — which is why
`blackbox_decode` emits `LOG.01.csv`, `LOG.02.csv` and so on, and why
`bfchirp` has a `--segment` flag.

The header carries the field names, per-field predictor and encoder indices,
and the firmware's configuration dump. That configuration dump is what
`bfchirp` reads settings from, via the `.headers.csv` sidecar that
`--save-headers` produces.

## Frame types

| Frame | Contents |
|---|---|
| `I` | Intraframe — a keyframe, decodable on its own |
| `P` | Interframe — predicted from previous frames |
| `G` / `H` | GPS position / GPS home reference |
| `S` | Slow frame — rarely-changing state (flight mode, failsafe) |
| `E` | Event — state transitions, e.g. in-flight PID adjustment |

`I` and `P` carry the flight data every analysis here uses, at the logging
rate. Both begin with `loopIteration` and `time`.

## Encoding, and why it matters downstream

Fields are compressed by subtracting a *predictor* (previous value, straight
line, average of the last two, motor[0], and others) and then applying an
*encoder* (signed/unsigned variable byte, Elias delta, several tagged
multi-field schemes). None of this survives decoding — the CSV holds plain
integers — but two consequences do:

**Values are raw sensor units, not physical units.** `gyroADC` comes out in
gyro ADC counts, scaled by the `gyro.scale` header. This is the origin of the
`--unit-rotation` trap described in
[blackbox-decode.md](blackbox-decode.md#the-flag-that-must-stay-off).

**There is no checksum, so corruption is detected heuristically.** The decoder
checks that the byte following a decoded frame is a valid frame-type letter,
and that `loopIteration` and `time` advance sensibly. On failure it skips to
the next intraframe. A damaged log therefore comes out *shorter* rather than
wrong — but with a gap. `bfchirp` computes `fs` from the mean sample interval
and works over a flight mask that assumes kept samples are largely contiguous,
so a heavily corrupted log will quietly misreport. Check the reported duration
and sample rate against what you flew.

## Column names in the decoded CSV

Two spellings are in circulation depending on decoder version and flags: bare
(`time`) and unit-suffixed (`time (us)`). Both appear in real files.
[`FlightLog`](../../src/bfchirp/log.py) registers both and looks columns up
through an alias map; code should go through it rather than indexing a raw
name.

Columns `bfchirp` uses:

| Column | Meaning |
|---|---|
| `time` / `time (us)` | Timestamp, microseconds |
| `gyroADC[0..2]` | Filtered gyro, roll/pitch/yaw |
| `gyroUnfilt[0..2]` | Pre-filter gyro — the noise analysis reference |
| `setpoint[0..3]` | Rate setpoint; `[3]` is throttle |
| `axisP/I/D/F[0..2]` | PID term contributions |
| `motor[0..3]` | Motor commands as sent to the ESCs |
| `eRPM[0..3]` | Electrical RPM / 100, bidirectional DShot only |
| `debug[0..3]` | Meaning depends on `debug_mode` |

`eRPM` is the other classic trap: it is electrical RPM divided by 100, so
mechanical RPM is `eRPM * 100 / (motor_poles / 2)`.

## Sources

Checked 2026-09-08 against betaflight/betaflight.com
[`f05cf72`](https://github.com/betaflight/betaflight.com/tree/f05cf72c7f48555607c271c588577dd5a65c5fd1):
`docs/development/Blackbox-Internals.md`
([rendered](https://betaflight.com/docs/development/Blackbox-Internals)); and
betaflight/betaflight
[`61b2c9f`](https://github.com/betaflight/betaflight/tree/61b2c9f6d98d7108d931289614e60b1947c2b0c6):
`src/main/blackbox/blackbox.c`, `src/main/blackbox/blackbox_fielddefs.h`.
