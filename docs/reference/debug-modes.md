# Debug modes and debug channels

Betaflight logs four generic `debug[0..3]` columns whose meaning depends
entirely on the single global `debug_mode` setting. One mode is active at a
time, so a log can answer chirp questions or gyro-internals questions, never
both.

## How the mechanism works

`debug_mode` is a lookup-table setting (`TABLE_DEBUG`) holding one value from
the `debugMode_e` enum in `src/main/build/debug.h`; the CLI names come from the
matching `debugModeNames[]` table in `debug.c`. Firmware code writes a channel
with `DEBUG_SET(DEBUG_<MODE>, index, value)`, which stores the value only when
that mode is the selected one.

The four channels are logged as blackbox fields `debug[0]`…`debug[3]` whenever
`debug_mode` is not `NONE` and the debug field group is enabled. They are
signed 16-bit, which is why almost every mode multiplies by a power of ten and
documents a unit rather than logging a float.

There are just over a hundred modes on current master. Only a few matter here.

## The modes `bfchirp` cares about

| `debug_mode` | Used by | What it gives you |
|---|---|---|
| `CHIRP` | chirp analysis | The sweep state: phase, axis, frequency, excitation |
| `NONE` | noise, step | Nothing — but both analyses work without debug channels |

The chirp channel map is documented in
[chirp-firmware.md](chirp-firmware.md#debug-channels-debug_mode--chirp).

That table is short for a reason worth stating plainly: **the noise and step
analyses do not use debug channels at all.** They read `gyroADC`, `gyroUnfilt`,
`setpoint`, `motor` and `eRPM`, which are first-class blackbox fields with
their own enable flags. See [cli-variables.md](cli-variables.md).

## `gyroUnfilt` is not a debug mode

This trips people up because it used to be one, and older guides still say so.

On current firmware `gyroUnfilt` is a **first-class blackbox field**, gated by
its own field-selection flag (`blackbox_disable_gyrounfilt`), not by
`debug_mode`. There is no `GYRO_SCALED` entry in `debugModeNames[]` on master —
the gyro-related modes that do exist are `GYRO_RAW`, `GYRO_FILTERED`,
`GYRO_SAMPLE`, `GYRO_CALIBRATION`, `MULTI_GYRO_RAW`, `MULTI_GYRO_DIFF` and
`MULTI_GYRO_SCALED`.

The practical consequence: to record a log for the noise analysis you enable a
field, you do not set a debug mode — which leaves `debug_mode` free for
`CHIRP`. See [recording.md](../recording.md).

## Reading debug channels from an unknown log

The channel meanings are not stored in the log. The blackbox header records the
numeric `debug_mode`, and the decoded CSV column headers are just
`debug[0]`…`debug[3]`. So a decoded log is only interpretable if you know which
mode was live — which is why `bfchirp` detects chirp logs from the *shape* of
the data (`debug[2]` non-zero over more than 5 % of samples) rather than
trusting the header. A log recorded in some other debug mode will not
accidentally look like a sweep.

Upstream maintains a `Debug-Field-Annotations.md` page describing per-mode
channel meanings; it is the place to look when adding support for a new mode.

## Sources

Checked 2026-09-08 against betaflight/betaflight
[`61b2c9f`](https://github.com/betaflight/betaflight/tree/61b2c9f6d98d7108d931289614e60b1947c2b0c6):
`src/main/build/debug.h`, `src/main/build/debug.c`, `src/main/flight/pid.c`,
`src/main/blackbox/blackbox.c`; and betaflight/betaflight.com
[`f05cf72`](https://github.com/betaflight/betaflight.com/tree/f05cf72c7f48555607c271c588577dd5a65c5fd1):
`docs/development/debugging/Debug-Field-Annotations.md`.
