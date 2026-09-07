# Recording a usable log

## For the noise analysis

* `set blackbox_disable_gyrounfilt = OFF` — logs `gyroUnfilt` alongside
  `gyroADC`. The raw/filtered pair is the whole point of the analysis; without
  it there is nothing to compare.

  Older guides tell you to `set debug_mode = GYRO_SCALED` for this. That mode
  no longer exists: `gyroUnfilt` is now a first-class blackbox field with its
  own enable flag. The change is a convenience — it leaves `debug_mode` free,
  so one log can serve both this analysis and a chirp. If you are on older
  firmware, check what your version offers before assuming either spelling.
* `set dshot_bidir = ON` — eRPM is what places the motor harmonics. Without it
  the harmonic columns are simply absent.
* Log at 2 kHz or better. Nothing above Nyquist is observable, and at 1 kHz the
  first motor harmonic of a 5-inch is already near the edge. `bfchirp` says so
  in the header when the rate is too low to see them.

## For the chirp analysis

* `set debug_mode = CHIRP`.
* `set f_roll = 0`, `set f_pitch = 0`, `set f_yaw = 0` on the swept axes.
  Feedforward differentiates the setpoint, so its output grows with frequency
  and the lead/lag compensator does not bound it. This is the one genuine
  safety precondition, and `bfchirp` reports whether it was met.

  (`bfchirp` calls this `ff_weight` because that is the name the blackbox
  *header* uses for the three feedforward gains. There is no `ff_weight` CLI
  setting — the settings are the per-axis `F` terms above.)
* Fly the sweeps in a steady hover, well clear of the ground: ground effect
  changes the plant, and the low end of the sweep moves the craft a long way.
* Record **many sweeps**. Four is enough to see the shape; twenty settles the
  ripple to where a 1 dB peak means something. This is the single most
  effective thing you can do for the quality of the result.

A good starting band is **0.2 → 15 Hz over 3 s**, which is what every result
quoted in this project was measured with:

```
set chirp_frequency_start_deci_hz = 2      # 0.2 Hz — remember: deci-Hz
set chirp_frequency_end_deci_hz   = 150    # 15 Hz
set chirp_time_seconds            = 3
```

Note that this is *not* the firmware default. Betaflight ships 0.2 Hz → 600 Hz
over 20 s, which is the generator's range rather than a recommendation — 600 Hz
is far above anything a rate loop can be identified at, and a 20 s sweep spends
most of its length there. Set the band deliberately.

Widening the band upward is mechanically gentler than it sounds — see the
motor-load discussion in the README — but do it only with feedforward off, and
read the motor-load table from your own craft afterwards rather than trusting
the general argument.

## Checking the log before trusting the numbers

`bfchirp` prints the settings that were live during the flight in its header,
because most surprising results turn out to be a setting rather than a
discovery. Read the header first:

* Is the sample rate high enough for what you are asking?
* Was feedforward really off during the sweeps?
* Do the PID and filter values match the tune you think you were testing?

Then read the coherence line. Below ~0.8 the response is not trustworthy at
that frequency — usually too little excitation there rather than a real feature
of the craft. Coherence will not, however, warn you about the dwell-starved top
of the sweep; see the limitations in the README.

## Where the settings come from

Every setting named here, with its range and default, is listed in
[reference/cli-variables.md](reference/cli-variables.md); it is checked against
a pinned Betaflight revision, so it can be re-verified rather than trusted.
