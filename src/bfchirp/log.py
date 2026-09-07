"""Flight-log configuration and column access."""

from __future__ import annotations

import csv as _csv
from dataclasses import dataclass, field

import numpy as np

try:  # pandas is ~10x faster on the large CSVs blackbox_decode emits
    import pandas as _pd
except ImportError:  # pragma: no cover
    _pd = None

AXES = ("Roll", "Pitch", "Yaw")


@dataclass
class Config:
    """Every setting that was live during the flight, from the log header."""

    raw: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_csv(cls, path: str) -> "Config":
        values: dict[str, str] = {}
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for row in _csv.reader(fh):
                if len(row) >= 2:
                    values[row[0].strip()] = row[1].strip()
        return cls(values)

    def get(self, key: str, default: str = "") -> str:
        return self.raw.get(key, default)

    def num(self, key: str, default: float = 0.0) -> float:
        """First numeric field of a setting (many are comma-separated triples)."""
        try:
            return float(self.raw[key].split(",")[0])
        except (KeyError, ValueError, IndexError):
            return default

    def nums(self, key: str) -> list[float]:
        try:
            return [float(x) for x in self.raw[key].split(",")]
        except (KeyError, ValueError):
            return []

    # -- convenience ------------------------------------------------------
    @property
    def craft(self) -> str:
        return self.get("Craft name") or "(unnamed)"

    @property
    def firmware(self) -> str:
        return self.get("Firmware revision", "?")

    @property
    def board(self) -> str:
        return self.get("Board information", "?")

    @property
    def motor_poles(self) -> int:
        return int(self.num("motor_poles", 14))

    @property
    def loop_hz(self) -> float:
        looptime = self.num("looptime", 0)
        return 1e6 / looptime if looptime else float("nan")

    @property
    def motor_range(self) -> tuple[float, float]:
        values = self.nums("motorOutput")
        return (values[0], values[1]) if len(values) == 2 else (0.0, 2047.0)

    @property
    def has_chirp_settings(self) -> bool:
        return "chirp_frequency_start_deci_hz" in self.raw

    @property
    def chirp_band_hz(self) -> tuple[float, float]:
        """Sweep bounds. The firmware stores these in deci-Hz, not Hz."""
        return (
            self.num("chirp_frequency_start_deci_hz", 0) / 10.0,
            self.num("chirp_frequency_end_deci_hz", 0) / 10.0,
        )


class FlightLog:
    """One decoded flight segment, with columns loaded on demand.

    Blackbox CSVs run to tens of megabytes and carry ~50 columns; every
    analysis needs a handful. Columns are therefore read lazily and cached.
    """

    def __init__(self, csv_path: str, config: Config, label: str):
        self.path = csv_path
        self.config = config
        self.label = label
        self._cache: dict[str, np.ndarray] = {}

        with open(csv_path, encoding="utf-8", errors="replace") as fh:
            header = fh.readline()
        self._names = [h.strip() for h in header.split(",")]
        # blackbox_decode may append a unit: "time (us)", "gyroADC[0] (deg/s)".
        # Both spellings are registered so callers can use either, and so the
        # same code works whether or not the decoder emitted units.
        self._alias = {name: name for name in self._names}
        self._alias.update({name.split(" (")[0]: name for name in self._names})

        self._load(["time"])
        seconds = self["time"] * 1e-6
        self.t = seconds - seconds[0]
        dt = float(np.median(np.diff(seconds))) if len(seconds) > 1 else float("nan")
        self.fs = 1.0 / dt if dt and dt > 0 else float("nan")
        self.duration = float(self.t[-1]) if len(self.t) else 0.0
        self.n = len(seconds)

    # -- column access ----------------------------------------------------
    def has(self, name: str) -> bool:
        return name in self._alias

    def _load(self, names) -> None:
        wanted = [n for n in names if n in self._alias and n not in self._cache]
        if not wanted:
            return
        columns = [self._names.index(self._alias[n]) for n in wanted]
        if _pd is not None:
            frame = _pd.read_csv(self.path, usecols=columns, header=0,
                                 skipinitialspace=True, dtype=np.float64)
            array = frame.to_numpy()
            # read_csv returns columns in file order, not in `columns` order
            for slot, k in enumerate(sorted(range(len(columns)), key=lambda i: columns[i])):
                self._cache[wanted[k]] = array[:, slot]
        else:
            array = np.loadtxt(self.path, delimiter=",", skiprows=1,
                               usecols=columns, ndmin=2)
            for k, name in enumerate(wanted):
                self._cache[name] = array[:, k]

    def __getitem__(self, name: str) -> np.ndarray:
        if name not in self._cache:
            self._load([name])
        if name not in self._cache:
            raise KeyError(f"column absent from log: {name}")
        return self._cache[name]

    def get(self, name: str, default=None):
        return self[name] if self.has(name) else default

    # -- derived quantities ----------------------------------------------
    @property
    def nyquist(self) -> float:
        return self.fs / 2.0

    def motor_rpm(self, index: int) -> np.ndarray:
        """Mechanical RPM of one motor.

        Blackbox stores eRPM as electrical RPM / 100, so the mechanical
        figure is ``eRPM * 100 / (poles / 2)``. Getting this wrong silently
        misplaces every motor harmonic.
        """
        column = f"eRPM[{index}]"
        if not self.has(column):
            return np.zeros(self.n)
        return self[column] * 100.0 / (self.config.motor_poles / 2.0)

    @property
    def rpm(self) -> np.ndarray:
        """Mean motor RPM — the overall rotor regime.

        Use this for anything that scales with rotation rate, such as motor
        harmonics. Do not use it to measure the *oscillation* a roll or pitch
        excitation causes: that drives the motors differentially, and the mean
        cancels it almost entirely. Take :meth:`motor_rpm` for that.
        """
        if "_rpm" in self._cache:
            return self._cache["_rpm"]
        names = [f"eRPM[{i}]" for i in range(4) if self.has(f"eRPM[{i}]")]
        if not names:
            self._cache["_rpm"] = np.zeros(self.n)
        else:
            self._load(names)
            erpm = np.mean([self[n] for n in names], axis=0)
            self._cache["_rpm"] = erpm * 100.0 / (self.config.motor_poles / 2.0)
        return self._cache["_rpm"]

    @property
    def throttle_pct(self) -> np.ndarray:
        """Throttle in percent. ``setpoint[3]`` is scaled 0..1000, not 0..2047."""
        if self.has("setpoint[3]"):
            return self["setpoint[3]"] / 10.0
        return np.zeros(self.n)

    @property
    def motors(self) -> np.ndarray:
        names = [f"motor[{i}]" for i in range(4) if self.has(f"motor[{i}]")]
        if not names:
            return np.zeros((0, self.n))
        self._load(names)
        return np.array([self[n] for n in names])

    def flight_mask(self, percentile: float = 30.0) -> np.ndarray:
        """Samples with the craft actually flying, excluding ground and idle.

        The comparison is inclusive on purpose: a perfectly steady hover puts
        every sample on the threshold, and a strict ``>`` would then keep
        nothing at all. Spectra computed over this mask assume the samples it
        keeps are largely contiguous, which holds for one continuous flight
        but not for a log stitched from scattered bursts.
        """
        rpm = self.rpm
        if not np.any(rpm > 0):
            return np.ones(self.n, dtype=bool)
        mask = rpm >= np.percentile(rpm[rpm > 0], percentile)
        return mask if mask.sum() > 0.05 * self.n else np.ones(self.n, dtype=bool)

    @property
    def is_chirp(self) -> bool:
        """True when the log carries a chirp sweep.

        ``debug[2]`` holds the instantaneous sweep frequency and is zero
        whenever no sweep is running, so a log with a meaningful fraction of
        non-zero samples is a chirp log regardless of the header.
        """
        if not (self.has("debug[2]") and self.has("debug[1]")):
            return False
        freq = self["debug[2]"]
        return bool(np.any(freq > 0) and np.mean(freq > 0) > 0.05)
