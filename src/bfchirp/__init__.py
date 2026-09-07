"""Quantitative analysis of Betaflight blackbox logs.

Three analyses, selected automatically from the log's contents:

``noise``
    Gyro spectra before and after filtering, motor harmonics derived from
    bidirectional-DShot eRPM, D-term noise, and what actually reaches the ESCs.

``step``
    Step response by Wiener deconvolution of setpoint into gyro: rise time,
    overshoot, delay, and tracking error normalised by flight aggressiveness.

``chirp``
    Full frequency response when the log contains a Betaflight chirp sweep:
    gain, phase, coherence, equivalent pure delay, phase margin, the excitation
    profile actually injected, and motor load versus frequency.
"""

from .log import Config, FlightLog
from .decode import decode, find_decoder
from .noise import NoiseResult, analyse_noise
from .step import StepResult, analyse_step
from .chirp import ChirpResult, analyse_chirp, chirp_segments

__version__ = "0.1.0"

__all__ = [
    "Config", "FlightLog", "decode", "find_decoder",
    "NoiseResult", "analyse_noise",
    "StepResult", "analyse_step",
    "ChirpResult", "analyse_chirp", "chirp_segments",
    "__version__",
]
