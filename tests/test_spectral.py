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

"""The shared signal-processing helpers."""

import numpy as np

from bfchirp.spectral import (band_rms, fit_pure_delay, log_bins,
                              phase_margin_from_peak, segment_length, spectrum)


def test_pure_delay_is_recovered_from_a_linear_phase():
    """A 10 ms delay is -3.6 degrees per Hz; the fit must return it."""
    freqs = np.linspace(1, 50, 200)
    phase = -360.0 * 0.010 * freqs
    tau_ms, r2 = fit_pure_delay(freqs, phase, 2.0, 45.0)
    assert np.isclose(tau_ms, 10.0, rtol=1e-6)
    assert r2 > 0.999


def test_pure_delay_declines_on_too_few_points():
    tau_ms, r2 = fit_pure_delay(np.array([1.0, 2.0]), np.array([0.0, -1.0]), 1.0, 2.0)
    assert np.isnan(tau_ms) and np.isnan(r2)


def test_phase_margin_falls_as_the_resonant_peak_grows():
    assert np.isnan(phase_margin_from_peak(0.0))       # no peak above unity
    assert phase_margin_from_peak(1.5) > phase_margin_from_peak(6.0)
    assert 0 < phase_margin_from_peak(6.0) < 60


def test_band_rms_matches_a_known_sine():
    fs, n = 2000.0, 20000
    t = np.arange(n) / fs
    x = 3.0 * np.sin(2 * np.pi * 120 * t)          # RMS = 3/sqrt(2)
    freqs, psd = spectrum(x, fs)
    assert np.isclose(band_rms(freqs, psd, 80, 200), 3.0 / np.sqrt(2), rtol=0.05)
    assert band_rms(freqs, psd, 300, 500) < 0.05   # nothing outside the band


def test_log_bins_span_the_range_and_grow_geometrically():
    bins = log_bins(1.0, 16.0, 4)
    assert len(bins) == 4
    assert np.isclose(bins[0][0], 1.0) and np.isclose(bins[-1][1], 16.0)
    ratios = [hi / lo for lo, hi in bins]
    assert np.allclose(ratios, ratios[0])


def test_segment_length_never_exceeds_the_data():
    assert segment_length(100) <= 100
    assert segment_length(100_000) == 2048
