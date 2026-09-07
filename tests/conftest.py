"""Synthetic logs, so the suite needs no flight data to run."""

from __future__ import annotations

import numpy as np
import pytest

from bfchirp.log import Config, FlightLog

FS = 2000.0

#: Transport delay built into the chirp fixture: 30 samples at 2 kHz = 15 ms.
DELAY_SAMPLES = 30
COLUMNS = (
    ["loopIteration", "time (us)"]
    + [f"axisP[{i}]" for i in range(3)]
    + [f"axisD[{i}]" for i in range(3)]
    + [f"axisF[{i}]" for i in range(3)]
    + [f"setpoint[{i}]" for i in range(4)]
    + [f"gyroADC[{i}]" for i in range(3)]
    + [f"gyroUnfilt[{i}]" for i in range(3)]
    + [f"debug[{i}]" for i in range(4)]
    + [f"motor[{i}]" for i in range(4)]
    + [f"eRPM[{i}]" for i in range(4)]
)

HEADERS = {
    "Craft name": "TestCraft",
    "Firmware revision": "Betaflight 2026.6.1 (test) STM32G474",
    "Board information": "TEST BOARD",
    "looptime": "125",
    "motor_poles": "12",
    "motorOutput": "0,2047",
    "rollPID": "45,80,30",
    "pitchPID": "47,84,34",
    "yawPID": "45,80,0",
    "ff_weight": "0,0,0",
    "chirp_frequency_start_deci_hz": "2",
    "chirp_frequency_end_deci_hz": "150",
    "chirp_time_seconds": "3",
    "chirp_amplitude_roll": "230",
    "chirp_amplitude_pitch": "230",
    "chirp_amplitude_yaw": "180",
    "chirp_lag_freq_hz": "3",
    "chirp_lead_freq_hz": "30",
}


def write_log(directory, table: dict, headers: dict | None = None,
              label: str = "synthetic") -> FlightLog:
    """Write a CSV plus its header sidecar and return the loaded log."""
    n = len(next(iter(table.values())))
    data = {name: np.zeros(n) for name in COLUMNS}
    data.update(table)
    csv_path = directory / f"{label}.csv"
    array = np.column_stack([data[name] for name in COLUMNS])
    with open(csv_path, "w", encoding="utf-8") as fh:
        fh.write(", ".join(COLUMNS) + "\n")
        np.savetxt(fh, array, delimiter=",", fmt="%.6f")

    merged = dict(HEADERS)
    merged.update(headers or {})
    with open(directory / f"{label}.headers.csv", "w", encoding="utf-8") as fh:
        for key, value in merged.items():
            fh.write(f'"{key}","{value}"\n')
    return FlightLog(str(csv_path), Config(merged), label)


def exponential_sweep(duration: float, f0: float, f1: float, fs: float = FS):
    """A Betaflight-style exponential sweep and its instantaneous frequency."""
    t = np.arange(int(duration * fs)) / fs
    k = (f1 / f0) ** (1.0 / duration)
    freq = f0 * k ** t
    phase = 2 * np.pi * f0 * (k ** t - 1) / np.log(k)
    return t, freq, np.sin(phase)


@pytest.fixture
def chirp_log(tmp_path):
    """A log whose loop is a known first-order lag, swept 0.2 → 15 Hz.

    Building the response from a known transfer function is what makes the
    chirp assertions meaningful: the measured delay must come back close to
    the delay that was put in.
    """
    quiet = int(FS * 1.0)
    sweeps = []
    for _ in range(4):
        _, freq, excitation = exponential_sweep(3.0, 0.2, 15.0)
        sweeps.append((freq, excitation))

    n = (len(sweeps[0][0]) + quiet) * len(sweeps)
    table = {name: np.zeros(n) for name in COLUMNS}
    table["time (us)"] = np.arange(n) / FS * 1e6
    table["eRPM[0]"] = np.full(n, 1800.0)
    table["eRPM[1]"] = np.full(n, 1800.0)
    table["eRPM[2]"] = np.full(n, 1800.0)
    table["eRPM[3]"] = np.full(n, 1800.0)
    for i in range(4):
        table[f"motor[{i}]"] = np.full(n, 900.0)

    # A pure transport delay is what the analysis claims to recover, so the
    # fixture injects one exactly: DELAY_SAMPLES at FS. The light first-order
    # lag on top only rolls the gain off, so the response is not trivially 0 dB.
    delay = DELAY_SAMPLES
    tau = 0.002
    alpha = (1.0 / FS) / (tau + 1.0 / FS)
    cursor = 0
    for freq, excitation in sweeps:
        length = len(freq)
        span = slice(cursor, cursor + length)
        setpoint = 230.0 * excitation
        shifted = np.r_[np.zeros(delay), setpoint[:-delay]]
        gyro = np.zeros(length)
        for k in range(1, length):
            gyro[k] = gyro[k - 1] + alpha * (shifted[k] - gyro[k - 1])
        table["setpoint[0]"][span] = setpoint
        table["gyroADC[0]"][span] = gyro
        table["gyroUnfilt[0]"][span] = gyro
        table["debug[1]"][span] = 0
        table["debug[2]"][span] = freq * 10.0     # deci-Hz, as the firmware logs it
        table["debug[3]"][span] = excitation * 1000.0
        # A roll excitation drives the two motor pairs in opposition, which is
        # exactly why the four-motor mean cannot be used to measure it.
        for i, sign in enumerate((1.0, 1.0, -1.0, -1.0)):
            table[f"motor[{i}]"][span] = 900.0 + sign * 0.2 * setpoint
            table[f"eRPM[{i}]"][span] = 1800.0 + sign * 2.0 * setpoint
        cursor += length + quiet

    return write_log(tmp_path, table, label="chirp")


@pytest.fixture
def noise_log(tmp_path):
    """A log with a 500 Hz tone present raw and removed after filtering."""
    n = int(FS * 20)
    t = np.arange(n) / FS
    rng = np.random.default_rng(0)
    tone = 12.0 * np.sin(2 * np.pi * 500 * t)
    base = rng.normal(0, 1.0, n)

    table = {name: np.zeros(n) for name in COLUMNS}
    table["time (us)"] = t * 1e6
    for i in range(3):
        table[f"gyroUnfilt[{i}]"] = base + tone
        table[f"gyroADC[{i}]"] = base
        table[f"axisD[{i}]"] = rng.normal(0, 5.0, n)
        # One second of stick input per axis, enough for the step windows.
        table[f"setpoint[{i}]"] = 150.0 * np.sin(2 * np.pi * 1.5 * t)
    for i in range(4):
        table[f"motor[{i}]"] = 900.0 + rng.normal(0, 20.0, n)
        # Held exactly steady: the flight mask must then keep the whole log,
        # and the spectra stay those of an uninterrupted time series.
        table[f"eRPM[{i}]"] = np.full(n, 1800.0)
    return write_log(tmp_path, table, label="noise")
