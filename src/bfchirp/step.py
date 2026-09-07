"""Step response by Wiener deconvolution."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .log import AXES, FlightLog

#: Windows quieter than this (deg/s RMS of setpoint) carry no usable excitation.
MIN_EXCITATION_DPS = 20.0

#: Wiener regularisation, as a fraction of mean input power. Larger values
#: suppress noise amplification where the input is weak, at the cost of
#: smoothing genuine detail.
WIENER_LAMBDA = 0.02


@dataclass
class StepResult:
    per_axis: dict
    fs: float
    quantisation_ms: float


def analyse_step(log: FlightLog, min_excitation: float = MIN_EXCITATION_DPS) -> StepResult:
    """Estimate the step response from ordinary flight, no test input needed.

    The impulse response is recovered by regularised deconvolution of gyro by
    setpoint over one-second windows, averaged over every window where the
    pilot actually moved the sticks; integrating it gives the step response.

    Caveat worth respecting: ``delay_ms`` is quantised to the log's sample
    period, so at 800 Hz every axis tends to land on the same multiple of
    1.25 ms. Compare delays only between logs recorded at the same rate.
    """
    fs = log.fs
    mask = log.flight_mask()
    window = int(fs * 1.0)
    per_axis: dict = {}

    for index, name in enumerate(AXES):
        sp_col, gyro_col = f"setpoint[{index}]", f"gyroADC[{index}]"
        if not (log.has(sp_col) and log.has(gyro_col)):
            continue
        setpoint, gyro = log[sp_col], log[gyro_col]

        impulses = []
        for start in range(0, len(setpoint) - window, window // 2):
            chunk = slice(start, start + window)
            if np.std(setpoint[chunk]) < min_excitation:
                continue
            taper = np.hanning(window)
            spectrum_in = np.fft.rfft(setpoint[chunk] * taper)
            spectrum_out = np.fft.rfft(gyro[chunk] * taper)
            lam = float(np.mean(np.abs(spectrum_in) ** 2)) * WIENER_LAMBDA
            impulses.append(np.fft.irfft(
                spectrum_out * np.conj(spectrum_in) / (np.abs(spectrum_in) ** 2 + lam)
            ))

        if len(impulses) < 3:
            per_axis[name] = {"ok": False, "windows": len(impulses)}
            continue

        impulse = np.mean(impulses, axis=0)
        step = np.cumsum(impulse)[: int(fs * 0.5)]
        steady = float(np.mean(step[int(fs * 0.2):]))
        if not np.isfinite(steady) or abs(steady) < 1e-9:
            per_axis[name] = {"ok": False, "windows": len(impulses)}
            continue
        step = step / steady

        times_ms = np.arange(len(step)) / fs * 1000.0
        i10 = int(np.argmax(step >= 0.1))
        i90 = int(np.argmax(step >= 0.9))
        peak = int(np.argmax(step))

        error = gyro[mask] - setpoint[mask]
        sp_rms = float(np.std(setpoint[mask]))
        per_axis[name] = {
            "ok": True,
            "windows": len(impulses),
            "rise_ms": float(times_ms[i90] - times_ms[i10]),
            "overshoot_pct": float((float(np.max(step)) - 1.0) * 100.0),
            "peak_ms": float(times_ms[peak]),
            "delay_ms": float(times_ms[i10]),
            "settle": float(step[-1]),
            "error_rms": float(np.std(error)),
            "setpoint_rms": sp_rms,
            # Normalising by flight aggressiveness is what makes two logs
            # comparable: a gentle flight always shows a smaller raw error.
            "error_normalised": float(np.std(error) / sp_rms) if sp_rms > 1e-6 else float("nan"),
        }

    return StepResult(per_axis, fs, 1000.0 / fs if fs else float("nan"))
