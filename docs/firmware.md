# What the firmware actually does

Verified against `src/main/flight/chirp.c` and `pid.c` in Betaflight, and
against real logs. [PR #13105][pr] is the reference.

[pr]: https://github.com/betaflight/betaflight/pull/13105

## The debug channels

With `debug_mode = CHIRP`:

| Channel | Contents | Scaling |
|---|---|---|
| `debug[0]` | sweep phase argument | `5000 × sinarg` |
| `debug[1]` | excited axis, `-1` when idle | raw axis index |
| `debug[2]` | instantaneous frequency | `10 × f`, i.e. **deci-Hz** |
| `debug[3]` | normalised excitation | `1000 × chirp` |

The deci-Hz scaling on `debug[2]` matters twice over: it is also how
`chirp_frequency_start_deci_hz` and `chirp_frequency_end_deci_hz` are stored in
the header. Reading either as Hz puts every frequency out by a factor of ten.

`debug[2]` is zero whenever no sweep is running, which is what `bfchirp` uses
to segment the log — the header alone cannot tell you a sweep was actually
flown.

## Is the chirp inside the logged setpoint?

Everything rests on this. If the setpoint were captured *before* the sweep was
added, `gyro / setpoint` would measure nothing real.

It is inside. Measured on an Air65 log:

```
correlation setpoint vs debug[3]    Roll +0.78   Pitch +0.79   Yaw +0.77
setpoint p99 during sweeps          245 deg/s
setpoint RMS outside sweeps           4.1 deg/s
```

A setpoint that goes from 4 deg/s RMS in hover to 245 deg/s peak during the
sweeps leaves no room for doubt.

## Why the injected amplitude is never the configured one

Two mechanisms shape it, and together they explain a deficit that looks like a
measurement error — on the Air65, a regression slope of 126 deg/s against a
nominal 230, identically on all three axes.

1. **Below 1 Hz the firmware scales the excitation down deliberately**
   (`if (fchirp < 1.0f) exc = fchirp * exc`), so the craft does not integrate
   too much angle at the very start of the sweep.
2. **A lead/lag compensator** shapes the rest. Its pole and zero are
   `chirp_lag_freq_hz` and `chirp_lead_freq_hz` (3 Hz and 30 Hz by default),
   so above the zero the amplitude floors at their ratio — 10 % of nominal.

Measured on a stock 0.2 → 15 Hz sweep:

| f (Hz) | injected | % of nominal |
|---|---|---|
| 0.2 – 0.4 | 35 deg/s | 15 % |
| 0.7 – 1.0 | 114 deg/s | 50 % |
| 1.3 – 2.4 | 259 deg/s | 112 % |
| 5.9 – 8.1 | 114 deg/s | 50 % |
| 11.0 – 15.0 | 68 deg/s | 29 % |

This is why `bfchirp` measures the profile instead of assuming a flat one: a
weak gain reading at 0.3 Hz is mostly a statement about the excitation.

## Why the four-motor mean cannot measure the load

A roll or pitch sweep drives the two motor pairs in opposition. Averaging all
four cancels the oscillation almost entirely and makes the rotor look as though
it stops following far earlier than it does. On the Air65, the same sweep gives:

| f (Hz) | motor[0] cmd | mean of 4 rotors | rotor 0 alone |
|---|---|---|---|
| 1.0 – 1.5 | 9 | 126 rpm | 147 rpm |
| 2.2 – 3.2 | 36 | 107 rpm | 1175 rpm |
| 10.2 – 15.0 | 88 | 33 rpm | 1135 rpm |

Pairing each command with *its own* rotor is what produces the real result: the
oscillation stays flat at ~1100 rpm while the command triples, so the following
gain collapses and the excitation stops doing mechanical work.
