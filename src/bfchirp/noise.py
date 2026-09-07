# This file is part of bfchirp.
#
# Copyright (C) 2026 Cedric
#
# bfchirp is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# bfchirp is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.

"""Gyro, D-term and motor noise analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .log import AXES, FlightLog
from .spectral import band_rms, dominant_peaks, spectrum

#: Band edges in Hz. Bands beyond Nyquist are dropped rather than reported empty.
BAND_EDGES = (20, 80, 200, 400, 800, 1200)


@dataclass
class NoiseResult:
    bands: list[tuple[float, float]]
    per_axis: dict
    rpm: dict
    motor: dict
    saturation_pct: float


def analyse_noise(log: FlightLog) -> NoiseResult:
    """Compare raw and filtered gyro band by band, against motor harmonics.

    The raw/filtered pair is what makes this meaningful: it separates how much
    noise the craft produces from how much the filter chain removes, and so
    shows whether there is headroom to filter less (and gain latency).
    """
    mask = log.flight_mask()
    fs, nyquist = log.fs, log.nyquist

    bands = [(lo, hi) for lo, hi in zip(BAND_EDGES[:-1], BAND_EDGES[1:])
             if hi <= nyquist + 1e-6]
    if not bands:
        bands = [(20.0, max(nyquist, 21.0))]

    rpm_flight = log.rpm[mask]
    rpm_info: dict = {}
    if np.any(rpm_flight > 0):
        p5, p95 = (float(x) for x in np.percentile(rpm_flight, [5, 95]))
        rpm_info = {
            "mean": float(np.mean(rpm_flight)),
            "p5": p5, "p95": p95, "max": float(np.max(log.rpm)),
            # Motor harmonics: H1 is the rotation rate, H2/H3 its multiples.
            "harmonics": {f"H{k}": (k * p5 / 60.0, k * p95 / 60.0) for k in (1, 2, 3)},
        }

    per_axis: dict = {}
    for index, name in enumerate(AXES):
        raw_col, filt_col = f"gyroUnfilt[{index}]", f"gyroADC[{index}]"
        if not (log.has(raw_col) and log.has(filt_col)):
            continue
        raw, filtered = log[raw_col][mask], log[filt_col][mask]
        freqs, psd_raw = spectrum(raw, fs)
        _, psd_filt = spectrum(filtered, fs)

        rows = []
        for lo, hi in bands:
            r = band_rms(freqs, psd_raw, lo, hi)
            f = band_rms(freqs, psd_filt, lo, hi)
            attenuation = 20 * np.log10(f / r) if r > 0 and f > 0 else float("nan")
            rows.append({"lo": lo, "hi": hi, "raw": r, "filtered": f,
                         "attenuation_db": float(attenuation)})

        entry = {
            "bands": rows,
            "peaks_raw": dominant_peaks(freqs, psd_raw, 40, min(nyquist, 1200)),
            "peaks_filtered": dominant_peaks(freqs, psd_filt, 40, min(nyquist, 1200),
                                             prominence=0.06),
        }

        d_col = f"axisD[{index}]"
        if log.has(d_col):
            d_term = log[d_col][mask]
            d_freqs, d_psd = spectrum(d_term, fs)
            entry["dterm_rms"] = float(np.std(d_term))
            entry["dterm_hf"] = band_rms(d_freqs, d_psd, 80, min(nyquist, 1000))
        per_axis[name] = entry

    motor_info: dict = {}
    saturation = 0.0
    motors = log.motors
    if motors.size:
        _, upper = log.config.motor_range
        saturation = 100.0 * float(np.mean(np.max(motors, axis=0) > upper - 40))
        m_freqs, m_psd = spectrum(motors[0][mask], fs)
        motor_info = {
            "rms": float(np.std(motors[0][mask])),
            "median": float(np.median(motors[:, mask])),
            "p99": float(np.percentile(motors[:, mask], 99)),
            "range": log.config.motor_range,
            "bands": [{"lo": lo, "hi": hi, "rms": band_rms(m_freqs, m_psd, lo, hi)}
                      for lo, hi in bands],
        }

    return NoiseResult(bands, per_axis, rpm_info, motor_info, saturation)
