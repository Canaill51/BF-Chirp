# Working on bfchirp

Analysis of Betaflight blackbox logs. Read `README.md` first — its
"Limitations worth knowing" section is the honest account of what these
measurements can and cannot support, and `docs/firmware.md` records what was
verified against the firmware source rather than assumed.

## Conventions

* **English** throughout: code, comments, docs, CLI output.
* Analysis and rendering stay separate. Modules in `noise.py`, `step.py` and
  `chirp.py` return dataclasses of plain numbers; `report.py` is the only
  place that formats. This is what lets `--json` exist without duplication.
* Comments explain *why*, and especially why an obvious alternative is wrong.
  Several of them mark real traps — deci-Hz scaling, eRPM conversion, the
  four-motor mean — that already caused wrong answers once.

## Traps that have bitten before

* `debug[2]` and the `chirp_frequency_*_deci_hz` header keys are in
  **deci-Hz**. Reading them as Hz puts everything out by ten.
* eRPM is electrical RPM / 100, so mechanical RPM is `eRPM * 100 / (poles/2)`.
* Use `log.motor_rpm(i)` — never the `log.rpm` mean — to measure the
  oscillation a roll or pitch excitation causes. The mean cancels it.
* `blackbox_decode` is called without `--unit-rotation`: converting units
  changes `gyroADC` but not `gyroUnfilt`, and the two silently stop being
  comparable.
* Column names may or may not carry a unit suffix (`time` vs `time (us)`).
  `FlightLog` registers both spellings; look columns up through it.

## Tests

```sh
pytest
```

Fixtures in `tests/conftest.py` build synthetic logs with known contents — a
tone that filtering removes, a sweep through a known 15 ms transport delay — so
assertions have a ground truth. When you change an estimator, check it against
that truth rather than against its previous output.

A real reference log (Air65, 21 sweeps) was used during development; its
results are quoted in `README.md` and `docs/firmware.md`. Flight data is
gitignored and lives outside the repo.
