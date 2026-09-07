# What the firmware actually does

What real logs confirm, over and above what the source says. The upstream
source itself — the generator, the parameters, the debug channel scalings — is
documented in [reference/chirp-firmware.md](reference/chirp-firmware.md),
pinned to a commit. This page holds the things source code alone cannot
settle: whether the logged signal is what you think it is, and what the craft
actually did.

Verified against `src/main/common/chirp.c` and `src/main/flight/pid.c` in
Betaflight, and against real logs. [PR #13105][pr] is the reference.

[pr]: https://github.com/betaflight/betaflight/pull/13105

## The debug channels

The channel map and its scalings are firmware facts, documented with their
source in
[reference/chirp-firmware.md](reference/chirp-firmware.md#debug-channels-debug_mode--chirp).
Two of them shape how `bfchirp` reads a log:

**`debug[2]` is in deci-Hz**, and so are the
`chirp_frequency_start_deci_hz` / `chirp_frequency_end_deci_hz` header keys.
Reading either as Hz puts every frequency out by a factor of ten.

**`debug[2]` is zero whenever no sweep is running**, which is what `bfchirp`
segments on. The header cannot substitute: it records what was configured, not
whether a sweep was ever flown — and a log may contain any number of them,
across any subset of the three axes.

## Is the chirp inside the logged setpoint?

Everything rests on this. If the setpoint were captured *before* the sweep was
added, `gyro / setpoint` would measure nothing real.

The firmware settles the first half: `pid.c` adds the excitation straight into
the setpoint variable, `currentPidSetpoint += currentChirp`. What source alone
cannot settle is whether the value the blackbox *logs* is sampled after that
addition. Measurement on an Air65 log says it is:

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

Note that `debug[3]` is logged *before* the compensator and before the
amplitude scaling, so it cannot be used to reconstruct what was injected — see
[reference/chirp-firmware.md](reference/chirp-firmware.md#the-signal-path-into-the-setpoint).

Measured on a 0.2 → 15 Hz sweep:

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
