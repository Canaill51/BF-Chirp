# The chirp generator in Betaflight

What the firmware actually computes, and which of its choices `bfchirp` depends
on. This page describes upstream code; `docs/firmware.md` records what was
additionally verified against real flight logs.

The generator was added in [PR #13105][pr]. It lives in
`src/main/common/chirp.c` and `chirp.h` — **not** `src/main/flight/`, where a
reader might reasonably look for it.

[pr]: https://github.com/betaflight/betaflight/pull/13105

## The sweep

`chirpInit(f0, f1, t1, looptimeUs)` sets up an exponential sweep from `f0` to
`f1` over `t1` seconds:

```
Ts   = looptimeUs * 1e-6          sample period
N    = t1 / Ts                    total samples
beta = (f1 / f0) ^ (1 / t1)       growth rate per second
k0   = 2*pi / ln(beta)
k1   = k0 * f0
```

`chirpUpdate()` then advances one sample at a time:

```
fchirp = f0 * beta ^ (count * Ts)     instantaneous frequency
sinarg = (k0 * fchirp - k1) mod 2*pi  phase
exc    = cos(sinarg)
if (fchirp < 1.0) exc *= fchirp       low-frequency taper
```

Two details matter for anything reading these logs.

**It is a cosine, not a sine.** The comment in the firmware gives the reason:
the gyro integral — the actual attitude — then oscillates around zero instead
of drifting away from it. A sine would leave the craft with a net angle offset
at every frequency.

**Below 1 Hz the excitation is scaled by the frequency itself.** At 0.2 Hz the
craft gets 20 % of the configured amplitude. This is deliberate for the same
reason: at low frequency a given rate command integrates into a large angle, so
the firmware trades amplitude for a bounded attitude excursion. It is the first
of the two mechanisms that make the injected amplitude differ from the
configured one.

`chirpUpdate()` returns `false` once `count == N`, and the axis then advances.

## The signal path into the setpoint

This is the ordering that governs how a log must be interpreted. In
`src/main/flight/pid.c`:

```
chirp         = chirpUpdate(...) -> pidRuntime.chirp.exc     raw, +/-1
chirpFiltered = phaseCompApply(&pidRuntime.chirpFilter, chirp)
currentChirp  = pidRuntime.chirpAmplitude[axis] * chirpFiltered
currentPidSetpoint += currentChirp
```

Two consequences follow, and both are load-bearing for `bfchirp`:

1. **The sweep is added into `currentPidSetpoint`**, so the setpoint the
   blackbox logs already contains it. That is what makes `gyro / setpoint` the
   true closed-loop response, with any upstream rate shaping cancelling out of
   the ratio. Everything this tool reports about the chirp rests on this single
   line.

2. **`debug[3]` is captured *before* the phase compensator and before the
   amplitude scaling.** So `debug[3] × chirp_amplitude_*` is *not* what was
   injected — the lead/lag sits between them. This is precisely why
   [chirp.py](../../src/bfchirp/chirp.py) measures the excitation profile by
   quadrature demodulation of the setpoint rather than reconstructing it from
   the configured amplitude.

The compensator is a lead/lag with its pole at `chirp_lag_freq_hz` and its zero
at `chirp_lead_freq_hz` (3 Hz and 30 Hz by default). Above the zero the
amplitude floors at the ratio of the two — 10 % of nominal. Together with the
sub-1 Hz taper this shapes the excitation into a hump: weak at the bottom,
weak at the top, full amplitude only in the middle. See `docs/firmware.md` for
the measured profile.

**Feedforward has no such bound.** It differentiates the setpoint, so its
contribution grows with frequency without limit. This is the one genuine safety
precondition for sweeping, and it is why `bfchirp` reports the logged
feedforward gains.

## Axis cycling

`chirpAxis` is static and advances roll -> pitch -> yaw -> roll each time
CHIRP_MODE is *released*, resetting the generator. While the mode is inactive
`debug[1]` reads `-1`.

`bfchirp` segments a log from `debug[2]` and `debug[1]` transitions rather than
from the header, because the header records what was configured, not what was
flown.

## Debug channels (`debug_mode = CHIRP`)

Scalings are the firmware's own, from the `DEBUG_SET` calls in `pid.c`:

| Channel | Contents | Scaling | Unit |
|---|---|---|---|
| `debug[0]` | sweep phase argument | `5000 x sinarg` | 0.0002 rad |
| `debug[1]` | active axis, `-1` when idle | raw index | 0 = roll, 1 = pitch, 2 = yaw |
| `debug[2]` | instantaneous frequency | `10 x fchirp` | **deci-Hz** |
| `debug[3]` | raw excitation, pre-compensator | `1000 x chirp` | 0.001 |

`debug[2]` is zero whenever no sweep is running, which is what makes it usable
as a segmentation signal.

The deci-Hz scaling on `debug[2]` is the same convention as the
`chirp_frequency_start_deci_hz` / `chirp_frequency_end_deci_hz` header keys.
Reading either as Hz puts every frequency out by a factor of ten.

## Parameters

Defaults from `pgResetFn_pidProfiles` in `pid.c`; ranges from `settings.c`.
All are PID-profile values, so they change with the profile.

| Setting | Default | Range | Notes |
|---|---|---|---|
| `chirp_lag_freq_hz` | 3 | 0–255 | compensator pole |
| `chirp_lead_freq_hz` | 30 | 0–255 | compensator zero; lag/lead = 10 % floor |
| `chirp_amplitude_roll` | 230 | 0–500 | deg/s, nominal |
| `chirp_amplitude_pitch` | 230 | 0–500 | deg/s, nominal |
| `chirp_amplitude_yaw` | 180 | 0–500 | deg/s, nominal |
| `chirp_frequency_start_deci_hz` | 2 (= 0.2 Hz) | 1–1000 (0.1–100 Hz) | |
| `chirp_frequency_end_deci_hz` | 6000 (= 600 Hz) | 1–10000 (0.1–1000 Hz) | |
| `chirp_time_seconds` | 20 | 1–255 | sweep duration |

The firmware default end frequency is 600 Hz. That is far above the band in
which a multirotor rate loop can be identified — and far above what the
0.2 Hz–15 Hz configuration used to validate `bfchirp` sweeps. The default is a
generator range, not a recommendation; see [recording.md](../recording.md) for
the band actually worth flying and why.

All eight keys are written into the blackbox header under exactly these names,
so `bfchirp` reads them back verbatim.

## Sources

Checked 2026-09-08 against betaflight/betaflight
[`61b2c9f`](https://github.com/betaflight/betaflight/tree/61b2c9f6d98d7108d931289614e60b1947c2b0c6):
`src/main/common/chirp.c`, `src/main/common/chirp.h`, `src/main/flight/pid.c`,
`src/main/cli/settings.c`, `src/main/fc/parameter_names.h`,
`src/main/blackbox/blackbox.c`. Fetch them with
`python scripts/fetch_upstream.py`.
