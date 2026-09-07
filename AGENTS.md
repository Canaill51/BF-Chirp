# bfchirp

Quantitative analysis of Betaflight blackbox logs: how much latency the filter
chain costs, how much phase margin is left, and what a wider sweep costs the
motors. Three analyses — noise, step response, and chirp system identification.

Read [`README.md`](README.md) first. Its **"Limitations worth knowing"**
section is the honest account of what these measurements can and cannot
support, and it is the standard the rest of the project is held to: claims here
are supposed to be defensible, with their weaknesses stated rather than left
for the reader to discover.

## Setup and commands

```sh
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m pytest      # 35 tests, all synthetic, ~13 s
.venv/bin/bfchirp --help
```

Python 3.10+. `numpy` and `scipy` are required; `pandas` is optional and only
makes CSV reading ~10x faster.

`pip install -e ".[dev]"` inside an activated venv works just as well. What
does *not* work on a current Ubuntu is installing into the system interpreter:
it is marked externally-managed (PEP 668), and `python3 -m venv` needs the
`python3.X-venv` package, which is not installed by default. `uv` sidesteps
both without root, which is why it is the command given above.

`blackbox_decode` is needed **only** to decode `.bbl` files. A pre-decoded
`.csv` skips it, and the test suite never invokes it — so a full test run
needs no external tooling.

There is no lint or format configuration in this repository. Match the style
of the surrounding code rather than reformatting it.

## The one architectural rule

**Analysis and rendering stay separate.**

`noise.py`, `step.py` and `chirp.py` return dataclasses of plain numbers.
[`report.py`](src/bfchirp/report.py) is the only place that formats anything.

This is what lets `--json` exist without duplicating a single computation. So:
do not format inside an analysis module, and do not compute inside
`report.py`. If a reported figure needs a new derived value, it belongs in the
dataclass, not in the renderer.

## Traps that have bitten before

Each of these produced a wrong answer at least once. Several are marked with
comments in the code for the same reason.

* **Deci-Hz.** `debug[2]` and the `chirp_frequency_*_deci_hz` header keys are
  in deci-Hz. Reading them as Hz puts everything out by ten.
  → [chirp-firmware.md](docs/reference/chirp-firmware.md#debug-channels-debug_mode--chirp)

* **eRPM.** It is electrical RPM / 100, so mechanical RPM is
  `eRPM * 100 / (poles / 2)`. A wrong `motor_poles` scales every RPM figure.
  → [blackbox-format.md](docs/reference/blackbox-format.md#column-names-in-the-decoded-csv)

* **The four-motor mean.** Use `log.motor_rpm(i)`, never the `log.rpm` mean, to
  measure the oscillation a roll or pitch excitation causes. Those excitations
  drive the motor pairs in opposition, so the mean cancels them and the rotor
  looks like it stopped following long before it did.
  → [`docs/firmware.md`](docs/firmware.md#why-the-four-motor-mean-cannot-measure-the-load)

* **`--unit-rotation`.** `blackbox_decode` is called without it, deliberately.
  The conversion changes `gyroADC` but not `gyroUnfilt`, and the two silently
  stop being comparable — which is the entire basis of the noise analysis.
  → [blackbox-decode.md](docs/reference/blackbox-decode.md#the-flag-that-must-stay-off)

* **Column name spellings.** Names may or may not carry a unit suffix (`time`
  vs `time (us)`). `FlightLog` registers both; look columns up through it
  rather than indexing a raw name.

## Conventions

* **English** throughout: code, comments, docs, CLI output.
* Comments explain *why*, and especially why an obvious alternative is wrong.
  A comment restating what the line already says is noise; one recording a trap
  is the most valuable thing in the file.
* Reported numbers come with their own quality indicator where one exists
  (coherence, R², window count). A figure the data cannot support should say so
  rather than be printed bare.

## Tests

```sh
pytest
```

Fixtures in `tests/conftest.py` build synthetic logs with **known contents** —
a tone that filtering removes, a sweep through an exact 15 ms transport delay,
motors driven differentially so the four-motor-mean trap stays testable.

When you change an estimator, check it against that ground truth, not against
its previous output. A test that asserts the current behaviour only tells you
the code did not change; these fixtures tell you whether it is right.

## Documentation

| File | Purpose |
|---|---|
| [README.md](README.md) | What it measures, sample output, and the limitations |
| [docs/recording.md](docs/recording.md) | How to record a log worth analysing |
| [docs/firmware.md](docs/firmware.md) | What was verified against **real logs** |
| [docs/reference/](docs/reference/) | What was verified against **upstream source**, with pinned commits |

The split between the last two is deliberate: `docs/firmware.md` holds
measurements that source code cannot settle, `docs/reference/` holds facts that
source code settles definitively. Keep new material on the correct side.

## Checking your work

Four steps, in order. The second is the one people skip.

1. **Run the tests.**

   ```sh
   .venv/bin/python -m pytest
   ```

   Against the ground truth described above, not against previous output.

2. **Check for upstream drift** — always when the change touches
   `docs/reference/`, states a fact about the firmware or the log format, or
   relies on one; and periodically otherwise, since drift arrives on
   Betaflight's schedule rather than yours.

   ```sh
   python scripts/fetch_upstream.py --check
   ```

   It re-fetches every pinned file at upstream `master` and reports which have
   moved. Needs network; takes seconds.

   If it reports drift, **read the changed file before touching anything
   else**. The reference page may still be correct, may need a correction, or
   may have been quietly wrong since the change landed — and only reading
   settles which. Then update the `commit` and `checked` fields in
   `scripts/upstream_sources.json`. Bumping the pin first turns a caught
   problem into a hidden one; the procedure is spelled out in
   [docs/reference/README.md](docs/reference/README.md#keeping-these-pages-honest).

   A clean run is worth recording in the commit message, the same way a test
   result is. It is the evidence that a firmware claim was true at that commit
   rather than remembered.

3. **Do not reformat.** There is no linter configured, so a formatting diff is
   noise the reviewer has to read past. Match the surrounding style.

4. **Report what actually happened.** If the tests failed, say so with the
   output; if a step was skipped, say which and why. A limitation found while
   working belongs in the README's limitations section rather than left
   implicit — that section is the project's main quality claim, and it is only
   worth anything if things get added to it.

## Out of bounds

* **Never commit flight data.** Logs and decoded CSVs are gitignored and live
  outside the repository. The Air65 reference log quoted throughout the docs is
  not in here and is not going to be.
* Nothing from Betaflight or blackbox-tools is committed either. Not a
  licensing matter — this project is GPL-3.0-or-later too — but a staleness
  one: fetch them with `scripts/fetch_upstream.py` and cite them. See
  [docs/reference/README.md](docs/reference/README.md#why-nothing-upstream-is-committed-here).
