"""Hardware adapters for the Raspberry Pi. NOT TESTED ON REAL HARDWARE.

Nothing here runs at import time, so the rest of the package works on a laptop.
Motors are deliberately not wired up: coordination decisions are logged only.
"""

from __future__ import annotations

import os
import sys
from typing import Callable

LEGACY_CODE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "In Progress (Code)")


def hcsr04_reader(code_dir: str = LEGACY_CODE_DIR) -> Callable[[], float]:
    """Return a ``read_cm()`` backed by the repo's existing ``ultrasonic.py`` (HC-SR04).

    Uses the pin numbers in ``In Progress (Code)/config.py`` (TRIG 4, ECHO 25). Those are
    what the author wrote down; they have not been verified against the wiring.
    The legacy driver returns ``999`` for "no echo"; ``carcomms.sensors`` handles that.
    """
    try:
        import RPi.GPIO as GPIO  # type: ignore
    except ImportError as exc:
        raise RuntimeError("RPi.GPIO is not installed: --sensor hcsr04 only works on a Raspberry Pi "
                           "(pip install -r requirements.txt there)") from exc
    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    import ultrasonic  # type: ignore  # legacy module, imported lazily on purpose

    ultrasonic.setup_ultrasonic()
    return ultrasonic.get_distance
