"""Distance-sensor adapter: turns raw readings into a trustworthy yes/no/unknown.

The legacy ``ultrasonic.get_distance()`` returns the number ``999`` for "no
echo", which is ambiguous: it can mean "nothing within range" or "the sensor
is unplugged". This module keeps that ambiguity visible instead of silently
treating it as "clear".
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Tuple

# HC-SR04 datasheet range. Readings outside it are not measurements.
HC_SR04_MIN_CM = 2.0
HC_SR04_MAX_CM = 400.0
LEGACY_NO_ECHO_CM = 999


class SensorStatus(Enum):
    OK = "ok"              # a plausible measurement
    NO_ECHO = "no_echo"    # sensor ran but heard nothing (far away *or* broken)
    INVALID = "invalid"    # NaN, negative, out of range, wrong type, read error


@dataclass(frozen=True)
class DistanceReading:
    status: SensorStatus
    distance_cm: Optional[float]
    timestamp: float


def classify_raw(raw: Any, now: float, *, min_cm: float = HC_SR04_MIN_CM,
                 max_cm: float = HC_SR04_MAX_CM) -> DistanceReading:
    """Classify one raw reading taken at time ``now``."""
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return DistanceReading(SensorStatus.INVALID, None, now)
    if isinstance(raw, float) and not math.isfinite(raw):
        return DistanceReading(SensorStatus.INVALID, None, now)
    if raw == LEGACY_NO_ECHO_CM:
        return DistanceReading(SensorStatus.NO_ECHO, None, now)
    if raw < min_cm or raw > max_cm:
        return DistanceReading(SensorStatus.INVALID, None, now)
    return DistanceReading(SensorStatus.OK, float(raw), now)


def read_safely(read_cm: Callable[[], Any], now: float) -> DistanceReading:
    """Call a hardware read function; any exception becomes an INVALID reading."""
    try:
        return classify_raw(read_cm(), now)
    except Exception:  # hardware drivers raise many things; all mean "no trustworthy value"
        return DistanceReading(SensorStatus.INVALID, None, now)


def path_clear(reading: Optional[DistanceReading], now: float, *, clear_cm: float,
               max_age_s: float, no_echo_is_clear: bool = False) -> Tuple[bool, str]:
    """Decide whether the way ahead is known to be clear.

    Returns ``(clear, reason)``. Anything unknown is *not* clear.
    """
    if reading is None:
        return False, "no distance reading"
    age = now - reading.timestamp
    if age > max_age_s:
        return False, f"distance reading stale ({age:.2f}s old)"
    if reading.status is SensorStatus.INVALID:
        return False, "distance reading invalid"
    if reading.status is SensorStatus.NO_ECHO:
        if no_echo_is_clear:
            return True, "no echo (treated as clear by configuration)"
        return False, "no echo: cannot tell clear from sensor fault"
    assert reading.distance_cm is not None
    if reading.distance_cm < clear_cm:
        return False, f"obstacle {reading.distance_cm:.0f} cm ahead"
    return True, f"clear ({reading.distance_cm:.0f} cm)"
