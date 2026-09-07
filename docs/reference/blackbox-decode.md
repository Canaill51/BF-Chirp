# `blackbox_decode`

The external tool that turns a binary `.bbl` into CSV. `bfchirp` needs it only
for `.bbl` input; a pre-decoded `.csv` skips it entirely, and the test suite
never invokes it.

## How `bfchirp` calls it

```
blackbox_decode --save-headers --output-dir <dir> <log.bbl>
```

That is the whole invocation, from [decode.py](../../src/bfchirp/decode.py).
Every flag is load-bearing and, just as importantly, every flag *not* there is
deliberate.

- `--save-headers` writes a `<name>.NN.headers.csv` sidecar containing the
  firmware's configuration dump. This is where every setting `bfchirp` reports
  comes from — without it there is no craft name, no filter configuration, and
  no `chirp_*` values.
- `--output-dir` keeps decoded CSVs out of the directory holding the original
  logs, so a temporary working directory can be cleaned up afterwards.

One log file yields one CSV per arm/disarm segment (`LOG.01.csv`,
`LOG.02.csv`, …). `bfchirp` builds a `FlightLog` per segment and `--segment N`
selects one.

## The flag that must stay off

**`--unit-rotation` must not be passed.** Its default is `raw`, and it must
stay there.

The conversion applies to `gyroADC` but **not** to `gyroUnfilt`. Pass
`--unit-rotation deg/s` and the two columns are silently in different units —
whereupon the noise analysis, whose entire purpose is comparing them band by
band, reports a filter attenuation figure that is really a unit-conversion
factor. Nothing errors; the numbers just become wrong.

The same caution applies to `--unit-acceleration` and `--unit-frame-time`:
`bfchirp` assumes microseconds for `time` and raw counts elsewhere. Leave the
unit flags alone.

## Getting a binary

Built from [betaflight/blackbox-tools][tools] (GPL-3.0). Prebuilt binaries for
macOS and Windows are on that repository's releases page; on Linux you build
from source. [PIDtoolbox][pt] also bundles one, which is where the search paths
below come from.

`bfchirp` looks in, in order: an explicit `--decoder PATH`, then
`~/.local/share/PIDtoolboxProV094/blackbox_decode`,
`~/.local/share/PIDtoolbox/blackbox_decode`, `/usr/local/bin/blackbox_decode`,
`/usr/bin/blackbox_decode`, then `$PATH`.

[tools]: https://github.com/betaflight/blackbox-tools
[pt]: https://github.com/skoch1s/PIDtoolbox

## Full option list

From the `--help` text in `src/blackbox_decode.c`. Note that the pasted
`--help` block in the upstream `Readme.md` is out of date: it omits
`--save-headers` and `--output-dir`, both of which exist in the source and
both of which `bfchirp` depends on. Trust the binary, not the Readme.

```
--help                   This page
--index <num>            Choose the log from the file to decode (or omit for all)
--limits                 Print the limits and range of each field
--stdout                 Write log to stdout instead of to a file
--output-dir <dir>       Directory to write output CSV files to
--unit-amperage <unit>   raw|mA|A                      default A
--unit-flags <unit>      raw|flags                     default flags
--unit-frame-time <unit> us|s                          default us
--unit-height <unit>     m|cm|ft                       default cm
--unit-rotation <unit>   raw|deg/s|rad/s               default raw   <- leave alone
--unit-acceleration <u>  raw|g|m/s2                    default raw   <- leave alone
--unit-gps-speed <unit>  mps|kph|mph                   default mps
--unit-vbat <unit>       raw|mV|V                      default V
--alt-offset             Altitude offset (meters), default zero
--merge-gps              Merge GPS data into the main CSV
--simulate-current-meter Simulate a current meter from throttle data
--sim-current-meter-scale    Override the FC's current meter scale
--sim-current-meter-offset   Override the FC's current meter offset
--save-headers           Save the log headers to a CSV file
--simulate-imu           Compute tilt/roll/heading from gyro/accel/mag
--include-imu-degrees    Include (deg) in the header for tilt/roll/heading
--imu-ignore-mag         Ignore magnetometer when computing heading
--declination <val>      Magnetic declination, degrees.minutes
--declination-dec <val>  Magnetic declination, decimal degrees
--debug                  Show extra debugging information
--raw                    Don't apply predictions (show raw field deltas)
```

`--include-imu-degrees` is a reminder of why column-name aliasing exists: some
flags change the header spelling of a column rather than only its values.

## Sources

Checked 2026-09-08 against betaflight/blackbox-tools
[`f832acf`](https://github.com/betaflight/blackbox-tools/tree/f832acf9cd9dbe5ad8220de1a5f4eb4021523d72):
`src/blackbox_decode.c`, `Readme.md`.
