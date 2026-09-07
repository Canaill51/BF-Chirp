# bfchirp

Quantitative analysis of Betaflight blackbox logs: filter noise, step response,
and full closed-loop frequency identification from the firmware's own chirp
sweep.

It answers the questions a tune actually turns on — *how much latency is my
filtering costing, how much phase margin do I have left, and what does a wider
sweep cost the motors* — with numbers you can defend, rather than by eye on a
spectrogram.

```
$ bfchirp Air65.bbl

FREQUENCY SWEEP — closed-loop response, setpoint into gyro
------------------------------------------------------------------------------
  21 sweeps · 0.2 → 15.0 Hz in 3 s · amplitude 230/230/180 deg/s
  lead/lag compensator 3 Hz / 30 Hz → excitation floors at 10 % of nominal above the zero
  usable band 1.5 → 15.0 Hz (below 1.5 Hz the firmware attenuates the excitation itself)

  axis        delay     R²                 peak  φ margin    gain top   φ top
  Roll       13.5ms  0.998      flat (±0.58 dB)        —°     -0.91dB    -70°
  Pitch      18.4ms  0.998      flat (±1.05 dB)        —°     -1.42dB    -94°
  Yaw        15.2ms  0.994    +1.53 dB @ 6.0 Hz     49.6°     -0.88dB    -66°
  minimum coherence: Roll 0.995 · Pitch 0.985 · Yaw 0.996
```

The repository is named `BF-Chirp`; the Python package and the command it
installs are both `bfchirp`.

## Install

```sh
pip install -e .          # add [dev] for the test suite
```

Python 3.10+, numpy and scipy. pandas is optional and roughly ten times faster
on the large CSVs `blackbox_decode` emits.

Decoding `.bbl` files needs `blackbox_decode` from
[blackbox-tools](https://github.com/betaflight/blackbox-tools). PIDtoolbox
ships one, and the usual locations are searched automatically; otherwise pass
`--decoder PATH`. Already-decoded `.csv` files need no decoder at all.

## Use

```sh
bfchirp flight.bbl                    # every analysis the log supports
bfchirp logs/ --only noise,step       # a directory, a subset of analyses
bfchirp flight.csv --json out.json    # machine-readable alongside the report
bfchirp flight.bbl --segment 2        # one arm/disarm segment of a .bbl
```

## The three analyses

Each one is skipped silently when the log cannot support it, so a plain flight
log and a chirp log can be passed to the same command.

### Noise

Gyro spectra **before and after** filtering, band by band, next to the motor
harmonics derived from bidirectional-DShot eRPM. The raw/filtered pair is the
point: it separates how much noise the craft produces from how much the filter
chain removes, which is what tells you whether there is room to filter less and
buy back latency. Also reports D-term noise and what actually reaches the ESCs.

Needs `debug_mode = GYRO_SCALED` (or any mode logging `gyroUnfilt`) for the raw
trace, and bidirectional DShot for the harmonics.

### Step response

Rise time, overshoot, delay and tracking error, recovered from ordinary flight
by regularised (Wiener) deconvolution of setpoint into gyro — no test input
needed. The tracking error is normalised by how hard the flight was actually
flown, which is what makes two different flights comparable.

`delay_ms` is quantised to the log's sample period, so only compare delays
between logs recorded at the same rate.

### Chirp

The real measurement. Betaflight's chirp generator ([PR #13105][pr]) adds an
exponential sweep to `currentPidSetpoint` and logs its state on the debug
channels. Because the logged setpoint *includes* the injected sweep,
`gyro / setpoint` is the true closed-loop response and any upstream shaping
cancels out of it.

Cross- and auto-spectra are accumulated across every sweep of an axis before
the ratio is taken (`H = <YX*> / <|X|²>`), which is far steadier than averaging
individual transfer-function estimates. Coherence falls out of the same
accumulators and is the measurement's own quality check.

Reported per axis: gain, phase and coherence curves; the equivalent pure delay
with the R² of that fit; the resonant peak and the phase margin it implies; and
the frequency where the fitted delay alone would reach −180°.

Set `debug_mode = CHIRP` to record one.

[pr]: https://github.com/betaflight/betaflight/pull/13105

## Two things the sweep will tell you that a spectrogram will not

**The excitation is never flat, by design.** The firmware scales it down below
1 Hz, then a lead/lag compensator rolls it off between its pole and its zero.
On a stock 0.2 → 15 Hz sweep the injected amplitude runs from ~15 % of nominal
at 0.2 Hz up to ~110 % near 2 Hz and back down to ~30 % at 15 Hz. A weak gain
reading where only 15 % of nominal was asked for says very little about the
craft. `bfchirp` measures the profile rather than assuming it.

**A wider sweep is mechanically gentler than the part you already fly.** The
motor-load table pairs each motor's command amplitude with *its own* rotor's
RPM oscillation. On an Air65 the command triples from 1 to 15 Hz while the RPM
oscillation stays flat at ~1100 rpm: the following gain collapses from ~32 to
~13 rpm/step, because past the rotor's bandwidth the command stops producing
acceleration and becomes current ripple. What wears a motor is angular
acceleration, so the most demanding part of a sweep is its low end — which a
stock sweep already covers.

One precondition: **feedforward must be off.** It differentiates the setpoint,
so its output grows with frequency and the lead/lag does not bound it.
`bfchirp` checks `ff_weight` and says so.

## Limitations worth knowing

* **The top of the band is the least reliable part of the measurement**, and it
  is where you most want to read it. An exponential sweep barely dwells at its
  highest frequencies. Against a known synthetic system the error grows toward
  the top of the band — about 1.7 dB at 15 Hz with four sweeps — and
  **coherence does not catch it**: it stayed at 0.999 in that noiseless test.
  More sweeps is the only real remedy.
* **Ripple can fake a resonance.** With four sweeps the estimate carries
  ~±0.8 dB of ripple, enough to produce an apparent peak and a phase margin
  derived from it. Twenty-one sweeps on real data settle well below that. Treat
  a peak under ~1 dB from a short log as noise.
* `f180_hz` is optimistic by construction: it extrapolates a pure delay, while
  filters and structural modes add phase beyond the measured band. The real
  crossing comes earlier.
* Phase margin from peak height assumes a dominant second-order mode. It is a
  well-behaved approximation for multirotor rate loops, not a Nyquist plot.
* Spectra are computed over a flight mask and assume the samples it keeps are
  largely contiguous — true for one continuous flight, not for a log stitched
  from scattered bursts.

## Development

```sh
pip install -e ".[dev]"
pytest
```

The suite builds synthetic logs with known contents — a tone that filtering
removes, a sweep through a known transport delay — so it runs without any
flight data and the assertions have a ground truth to check against.

## Layout

| Module | Contents |
|---|---|
| `log.py` | Header parsing, lazy column access, unit conversion, flight mask |
| `decode.py` | Locating and driving `blackbox_decode` |
| `spectral.py` | Welch spectra, band RMS, delay fit, phase margin |
| `noise.py` | Raw vs filtered gyro, motor harmonics, D-term, ESC noise |
| `step.py` | Wiener deconvolution and step metrics |
| `chirp.py` | Sweep segmentation, transfer function, excitation profile, motor load |
| `report.py` | Plain-text rendering and JSON conversion |
| `cli.py` | Command-line entry point |

## Licence

GNU General Public License v3.0 or later, the same licence Betaflight uses.
See [LICENSE](LICENSE).
