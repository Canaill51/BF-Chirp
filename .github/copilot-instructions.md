# Copilot instructions for bfchirp

**Read [`AGENTS.md`](../AGENTS.md) first.** It is the canonical brief for this
repository; this file exists only so Copilot picks it up.

Python 3.10+, `numpy` and `scipy` required, `pandas` optional. Install with
`pip install -e ".[dev]"`, test with `pytest`. No linter is configured — match
the surrounding style.

The one rule that shapes the codebase: **analysis and rendering stay
separate.** `noise.py`, `step.py` and `chirp.py` return dataclasses of plain
numbers; `report.py` is the only place that formats. That separation is what
lets `--json` exist without duplicating any computation.

Four traps have caused wrong answers before, all documented in `AGENTS.md`
with links to the upstream evidence in `docs/reference/`:

* `debug[2]` and the `chirp_frequency_*_deci_hz` header keys are in **deci-Hz**.
* eRPM is electrical RPM / 100 — mechanical RPM is `eRPM * 100 / (poles / 2)`.
* Use `log.motor_rpm(i)`, never the `log.rpm` four-motor mean, for roll/pitch
  excitation; the mean cancels the oscillation being measured.
* `blackbox_decode` must be called **without** `--unit-rotation`; it converts
  `gyroADC` but not `gyroUnfilt`, silently breaking the noise analysis.

Tests assert against synthetic ground truth in `tests/conftest.py`, never
against previous output. Never commit flight logs or decoded CSVs.
