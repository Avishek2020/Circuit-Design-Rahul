"""
Temperature analysis — pure functions that operate on lists of reading dicts.
No database dependency; all inputs are plain Python dicts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence


# ── MKT constants ─────────────────────────────────────────────────────────────
# Standard activation energy for food / pharma stability calculations
_HA_J_MOL  = 83_144.0   # J/mol  (83.144 kJ/mol, ICH Q1E / ASTM E1_344)
_R_J_MOL_K = 8.314       # J/(mol·K)
_ABS_ZERO  = 273.15


def _parse_ts(ts: str | datetime) -> datetime:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    s = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class ExcursionWindow:
    """A contiguous run of readings outside the required temperature range."""
    index:              int             # 0-based window number for this shipment
    start_time:         datetime
    end_time:           datetime
    duration_minutes:   float
    peak_temperature:   float           # most extreme reading (furthest from range)
    peak_time:          datetime
    max_deviation:      float           # positive = above max; negative = below min
    direction:          str             # "above_max" | "below_min" | "mixed"
    readings_in_window: int
    avg_temperature:    float

    @property
    def is_above_max(self) -> bool:
        return self.direction in ("above_max", "mixed")

    @property
    def severity(self) -> str:
        d = abs(self.max_deviation)
        if d >= 10 or self.duration_minutes >= 90:
            return "critical"
        if d >= 5 or self.duration_minutes >= 45:
            return "high"
        if d >= 2 or self.duration_minutes >= 20:
            return "medium"
        return "low"

    def summary(self) -> str:
        return (
            f"Window #{self.index + 1}: {self.start_time.strftime('%Y-%m-%dT%H:%MZ')}–"
            f"{self.end_time.strftime('%H:%MZ')} "
            f"({self.duration_minutes:.0f} min) | "
            f"peak={self.peak_temperature:.1f}°C "
            f"({'+'  if self.max_deviation > 0 else ''}{self.max_deviation:.1f}°C) | "
            f"{self.severity.upper()}"
        )


@dataclass
class TemperatureAnalysis:
    """Full temperature analysis for one shipment transit."""
    shipment_id:       str
    required_min:      float
    required_max:      float
    total_readings:    int
    excursion_count:   int            # individual out-of-range readings
    excursion_windows: list[ExcursionWindow]
    max_temperature:   float
    min_temperature:   float
    avg_temperature:   float
    mkt_celsius:       float | None   # Mean Kinetic Temperature, or None if < 2 readings
    is_compliant:      bool           # no excursion windows

    @property
    def total_excursion_minutes(self) -> float:
        return sum(w.duration_minutes for w in self.excursion_windows)

    @property
    def worst_window(self) -> ExcursionWindow | None:
        if not self.excursion_windows:
            return None
        return max(self.excursion_windows, key=lambda w: abs(w.max_deviation))

    def evidence_lines(self) -> list[str]:
        lines = [
            f"Readings: {self.total_readings} | Excursion readings: {self.excursion_count} "
            f"({self.excursion_count / max(1, self.total_readings) * 100:.1f}%)",
            f"Temp range observed: {self.min_temperature:.1f}°C – {self.max_temperature:.1f}°C "
            f"(required: {self.required_min}°C – {self.required_max}°C)",
        ]
        if self.mkt_celsius is not None:
            lines.append(f"Mean Kinetic Temperature (MKT): {self.mkt_celsius:.2f}°C")
        if self.excursion_windows:
            lines.append(f"Excursion windows ({len(self.excursion_windows)}):")
            for w in self.excursion_windows:
                lines.append(f"  {w.summary()}")
        else:
            lines.append("No excursion windows detected — transit compliant.")
        return lines


# ── core algorithms ───────────────────────────────────────────────────────────

def calculate_mkt(
    readings: Sequence[dict],
    interval_hours: float = 0.25,       # 15-minute default
) -> float | None:
    """
    Calculate Mean Kinetic Temperature (°C) for a sequence of readings.

    Uses the ICH Q1E formula:
        Tk = ΔHa/R / ln( Σ Δt  /  Σ exp(-ΔHa/(R·Ti)) · Δt )
           = ΔHa/R / ln( n / Σ exp(-ΔHa/(R·Ti)) )

    Returns None if fewer than 2 readings are present.
    """
    temps = [r["temperature_celsius"] for r in readings if r.get("temperature_celsius") is not None]
    if len(temps) < 2:
        return None

    n     = len(temps)
    dt    = interval_hours
    sumdt = n * dt
    summand = sum(
        math.exp(-_HA_J_MOL / (_R_J_MOL_K * (t + _ABS_ZERO)))
        for t in temps
    )
    if summand <= 0:
        return None

    # Correct sign: ln(sumdt / (summand·dt)) = ln(n / Σ) which is positive → positive Tk
    mkt_k = (_HA_J_MOL / _R_J_MOL_K) / math.log(sumdt / (summand * dt))
    return round(mkt_k - _ABS_ZERO, 3)


def find_excursion_windows(
    readings: Sequence[dict],
    required_min: float,
    required_max: float,
) -> list[ExcursionWindow]:
    """
    Identify contiguous runs of out-of-range readings.
    Readings must be pre-sorted by timestamp (ascending).
    """
    sorted_rdgs = sorted(readings, key=lambda r: _parse_ts(r["timestamp"]))
    windows: list[ExcursionWindow] = []
    win_idx = 0

    i = 0
    while i < len(sorted_rdgs):
        r = sorted_rdgs[i]
        t = r["temperature_celsius"]
        if t < required_min or t > required_max:
            # Start of a new excursion window
            group = [r]
            j = i + 1
            while j < len(sorted_rdgs):
                nxt = sorted_rdgs[j]["temperature_celsius"]
                if nxt < required_min or nxt > required_max:
                    group.append(sorted_rdgs[j])
                    j += 1
                else:
                    break

            temps       = [g["temperature_celsius"] for g in group]
            timestamps  = [_parse_ts(g["timestamp"]) for g in group]
            start_ts    = timestamps[0]
            end_ts      = timestamps[-1]
            dur_minutes = (end_ts - start_ts).total_seconds() / 60

            # Determine deviation and direction
            above_devs  = [t - required_max for t in temps if t > required_max]
            below_devs  = [required_min - t for t in temps if t < required_min]

            if above_devs and below_devs:
                direction = "mixed"
                max_dev   = max(above_devs) if max(above_devs) >= max(below_devs) else -max(below_devs)
            elif above_devs:
                direction = "above_max"
                max_dev   = max(above_devs)
            else:
                direction = "below_min"
                max_dev   = -max(below_devs)   # negative = below min

            # Peak = reading with greatest deviation from range
            if direction == "below_min":
                peak_idx  = temps.index(min(temps))
            else:
                peak_idx  = temps.index(max(temps))
            peak_temp = temps[peak_idx]
            peak_ts   = timestamps[peak_idx]

            windows.append(ExcursionWindow(
                index              = win_idx,
                start_time         = start_ts,
                end_time           = end_ts,
                duration_minutes   = max(dur_minutes, 0),
                peak_temperature   = peak_temp,
                peak_time          = peak_ts,
                max_deviation      = round(max_dev, 2),
                direction          = direction,
                readings_in_window = len(group),
                avg_temperature    = round(sum(temps) / len(temps), 2),
            ))
            win_idx += 1
            i = j
        else:
            i += 1

    return windows


def analyze_temperature(
    shipment: dict,
    readings: Sequence[dict],
) -> TemperatureAnalysis:
    """
    Full temperature analysis for one shipment.
    *shipment* must have ``required_temp_min`` and ``required_temp_max``.
    """
    t_min = float(shipment["required_temp_min"])
    t_max = float(shipment["required_temp_max"])
    sid   = shipment["shipment_id"]

    if not readings:
        return TemperatureAnalysis(
            shipment_id=sid, required_min=t_min, required_max=t_max,
            total_readings=0, excursion_count=0, excursion_windows=[],
            max_temperature=float("nan"), min_temperature=float("nan"),
            avg_temperature=float("nan"), mkt_celsius=None, is_compliant=True,
        )

    temps   = [r["temperature_celsius"] for r in readings]
    exc_cnt = sum(1 for r in readings if r.get("is_excursion", False))
    windows = find_excursion_windows(readings, t_min, t_max)
    mkt     = calculate_mkt(readings)

    return TemperatureAnalysis(
        shipment_id       = sid,
        required_min      = t_min,
        required_max      = t_max,
        total_readings    = len(readings),
        excursion_count   = exc_cnt,
        excursion_windows = windows,
        max_temperature   = round(max(temps), 2),
        min_temperature   = round(min(temps), 2),
        avg_temperature   = round(sum(temps) / len(temps), 3),
        mkt_celsius       = mkt,
        is_compliant      = len(windows) == 0,
    )
