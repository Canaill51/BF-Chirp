# Betaflight settings that affect these measurements

Every setting `bfchirp` reads, sets, or reports on, with its real CLI name.
Ranges and defaults are from `src/main/cli/settings.c` and the `pgResetFn`
blocks that back them.

Set a value with `set <name> = <value>`, then `save`. Profile values change
with the active PID profile; master values are global.

## Chirp

All PID-profile values. See [chirp-firmware.md](chirp-firmware.md#parameters)
for the full table with defaults and what each one does to the signal.

```
set chirp_amplitude_roll  = 230      # deg/s nominal, 0-500
set chirp_amplitude_pitch = 230
set chirp_amplitude_yaw   = 180
set chirp_frequency_start_deci_hz = 2      # deci-Hz -> 0.2 Hz
set chirp_frequency_end_deci_hz   = 150    # deci-Hz -> 15 Hz
set chirp_time_seconds    = 3
set chirp_lag_freq_hz     = 3        # compensator pole
set chirp_lead_freq_hz    = 30       # compensator zero
```

The `_deci_hz` suffix is not decoration. `150` means 15 Hz.

Running a sweep also needs the **CHIRP** flight mode bound to a switch in
Modes. Releasing the switch ends the sweep and advances to the next axis.

## Feedforward

There is no `ff_weight` setting. `ff_weight` is a *blackbox header key* — the
log writes the three feedforward gains under that name — but the CLI settings
are the per-axis `F` terms:

```
set f_roll  = 0
set f_pitch = 0
set f_yaw   = 0
```

Zero these on the swept axes before chirping. Feedforward differentiates the
setpoint, so its output grows with frequency and the chirp lead/lag does not
bound it. `bfchirp` reads the `ff_weight` header and tells you whether the
precondition was met.

## Blackbox field selection

Fields are enabled by default and turned *off* individually. The ones that
matter here:

| Setting | Controls | Needed by |
|---|---|---|
| `blackbox_disable_gyrounfilt` | `gyroUnfilt` — pre-filter gyro | noise |
| `blackbox_disable_gyro` | `gyroADC` — post-filter gyro | noise, step, chirp |
| `blackbox_disable_setpoint` | `setpoint` | step, chirp |
| `blackbox_disable_motors` | `motor[n]` | noise, chirp motor load |
| `blackbox_disable_rpm` | `eRPM[n]` | noise harmonics, chirp motor load |
| `blackbox_disable_pids` | `axisP/I/D/F` | noise D-term, chirp motor load |
| `blackbox_disable_debug` | `debug[0..3]` | chirp |

All take `OFF` (log the field) or `ON` (drop it):

```
set blackbox_disable_gyrounfilt = OFF
```

`eRPM` additionally requires bidirectional DShot; the field is conditional on
`useDshotTelemetry`, so without it the columns are absent no matter what this
flag says.

## Telemetry and logging rate

```
set dshot_bidir = ON          # eRPM telemetry; required for motor harmonics
set debug_mode  = CHIRP       # or NONE for a noise/step log
```

Logging rate is set by the loop rate and the blackbox sample rate divider
(`blackbox_sample_rate`, exposed in the configurator as a fraction of the PID
loop). Log at 2 kHz or better for noise work: nothing above Nyquist is
observable, and at 1 kHz the first motor harmonic of a 5-inch is already near
the edge.

## Settings `bfchirp` reports but does not require

Read back from the header and printed so that a surprising result can be
traced to a setting rather than a discovery — filters especially, since they
are what the noise analysis is measuring the cost of:

`rollPID` / `pitchPID` / `yawPID`, `ff_weight`, `d_max`, `d_max_gain`,
`gyro_lpf1_static_hz`, `gyro_lpf1_dyn_hz`, `gyro_lpf2_static_hz`,
`dterm_lpf1_dyn_hz`, `dterm_lpf2_static_hz`, `dyn_notch_count`, `dyn_notch_q`,
`dyn_notch_min_hz`, `dyn_notch_max_hz`, `rpm_filter_harmonics`,
`motor_poles`, `motorOutput`.

`motor_poles` is not cosmetic: it is what converts eRPM into mechanical RPM
(`eRPM * 100 / (poles / 2)`), so a wrong value scales every reported RPM.

## Sources

Checked 2026-09-08 against betaflight/betaflight
[`61b2c9f`](https://github.com/betaflight/betaflight/tree/61b2c9f6d98d7108d931289614e60b1947c2b0c6):
`src/main/cli/settings.c`, `src/main/fc/parameter_names.h`,
`src/main/flight/pid.c`, `src/main/blackbox/blackbox.c`,
`src/main/blackbox/blackbox_fielddefs.h`.
