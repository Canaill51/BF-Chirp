"""Shared spectral helpers."""

from __future__ import annotations

import numpy as np
from scipy import signal

# numpy renamed trapz -> trapezoid in 2.0
_trapezoid = getattr(np, "trapezoid", None) or np.trapz


def segment_length(n: int, want: int = 2048) -> int:
    """Welch segment length that fits the data without going below 256."""
    if n < 256:
        return max(8, int(2 ** np.floor(np.log2(max(n, 8)))))
    return int(min(want, 2 ** int(np.floor(np.log2(n)))))


def spectrum(x: np.ndarray, fs: float, want: int = 2048):
    """Welch power spectral density."""
    return signal.welch(x, fs, nperseg=segment_length(len(x), want))


def band_rms(freqs: np.ndarray, psd: np.ndarray, lo: float, hi: float) -> float:
    """RMS of the signal restricted to ``[lo, hi)``, by integrating its PSD."""
    mask = (freqs >= lo) & (freqs < hi)
    if mask.sum() < 2:
        return float("nan")
    return float(np.sqrt(_trapezoid(psd[mask], freqs[mask])))


def dominant_peaks(freqs, psd, lo, hi, count=5, prominence=0.05) -> list[float]:
    """The strongest spectral peaks in a band, strongest first."""
    mask = (freqs > lo) & (freqs < hi)
    if mask.sum() < 8:
        return []
    peaks, _ = signal.find_peaks(psd[mask], prominence=float(np.max(psd[mask])) * prominence)
    pairs = sorted(zip(freqs[mask][peaks], psd[mask][peaks]), key=lambda p: -p[1])
    return [float(f) for f, _ in pairs[:count]]


def log_bins(lo: float, hi: float, count: int) -> list[tuple[float, float]]:
    """Logarithmically spaced bin edges, matching a log sweep's own spacing."""
    edges = np.exp(np.linspace(np.log(max(lo, 1e-3)), np.log(hi), count + 1))
    return list(zip(edges[:-1], edges[1:]))


def fit_pure_delay(freqs: np.ndarray, phase_deg: np.ndarray,
                   f_lo: float, f_hi: float) -> tuple[float, float]:
    """Fit a pure delay to a phase curve.

    A pure transport delay produces phase linear in frequency, so the slope
    gives the delay directly: ``tau = -slope / 360`` seconds. Returns
    ``(tau_ms, r_squared)``; an R² near 1 means the loop really does behave
    like a fixed delay over that band.
    """
    mask = (freqs >= f_lo) & (freqs <= f_hi)
    if mask.sum() < 5:
        return float("nan"), float("nan")
    design = np.vstack([freqs[mask], np.ones(int(mask.sum()))]).T
    slope, intercept = np.linalg.lstsq(design, phase_deg[mask], rcond=None)[0]
    predicted = design @ [slope, intercept]
    ss_res = float(np.sum((phase_deg[mask] - predicted) ** 2))
    ss_tot = float(np.sum((phase_deg[mask] - np.mean(phase_deg[mask])) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return -slope / 360.0 * 1000.0, r2


def phase_margin_from_peak(peak_db: float) -> float:
    """Phase margin estimated from closed-loop resonant peak height.

    For a system dominated by a second-order mode,
    ``PM ~= 2 * arcsin(1 / (2 * Mr))`` where ``Mr`` is the linear peak.
    An approximation, but a well-behaved one for multirotor rate loops.
    Returns NaN when there is no peak above unity gain.
    """
    mr = 10.0 ** (peak_db / 20.0)
    if mr <= 1.0:
        return float("nan")
    return float(np.degrees(2 * np.arcsin(min(1.0 / (2 * mr), 1.0))))
