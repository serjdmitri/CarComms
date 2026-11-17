"""Optional camera milestone: find a coloured stop-line marker in a frame.

This is an INTERFACE plus a deliberately simple detector that works on recorded
images (binary PPM files) or any frame object you can index as ``frame[y][x]``
returning ``(r, g, b)`` (nested lists, or a NumPy array from picamera2 if you
have one). It uses only the standard library.

What it is for: telling a car "the stop line marker is close, send your
request". What it is NOT: proof that the intersection is empty. Nothing here
decides that crossing is safe; the exclusive grant from ``Coordinator`` does.

All defaults are uncalibrated placeholders, not measured values. The example
frames in ``examples/frames`` are synthetic, drawn by ``synthetic_frame``.
Only every ``stride``-th pixel is examined (and validated). Not wired into the
vehicle loop yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

Pixel = Tuple[int, int, int]


@dataclass(frozen=True)
class MarkerResult:
    status: str                 # "FOUND" | "NOT_FOUND" | "INVALID"
    coverage: float             # fraction of sampled pixels matching the marker colour
    centroid_y: Optional[float]  # 0.0 = top of frame, 1.0 = bottom; None if not found
    at_stop_line: bool          # marker is large and low in the frame
    detail: str = ""


class StopLineDetector:
    def __init__(self, marker_rgb: Pixel = (200, 30, 30), tolerance: float = 90.0,
                 min_coverage: float = 0.01, stop_line_y: float = 0.65, stride: int = 2) -> None:
        self.marker_rgb = marker_rgb
        self.tolerance = tolerance          # Euclidean RGB distance; PLACEHOLDER, uncalibrated
        self.min_coverage = min_coverage    # PLACEHOLDER
        self.stop_line_y = stop_line_y      # PLACEHOLDER: centroid lower than this => "at the line"
        self.stride = max(1, stride)

    def detect(self, frame: Any) -> MarkerResult:
        try:
            h = len(frame)
            w = len(frame[0]) if h else 0
        except TypeError:
            return MarkerResult("INVALID", 0.0, None, False, "frame is not indexable")
        if h < 2 or w < 2:
            return MarkerResult("INVALID", 0.0, None, False, "frame too small or empty")
        mr, mg, mb = self.marker_rgb
        tol2 = self.tolerance ** 2
        total = hits = 0
        sum_y = 0.0
        for y in range(0, h, self.stride):
            row = frame[y]
            if len(row) != w:
                return MarkerResult("INVALID", 0.0, None, False, "ragged frame")
            for x in range(0, w, self.stride):
                try:
                    r, g, b = (int(c) for c in tuple(row[x])[:3])
                except (TypeError, ValueError):
                    return MarkerResult("INVALID", 0.0, None, False, "bad pixel value")
                if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                    return MarkerResult("INVALID", 0.0, None, False, "pixel out of 0-255 range")
                total += 1
                if (r - mr) ** 2 + (g - mg) ** 2 + (b - mb) ** 2 <= tol2:
                    hits += 1
                    sum_y += y / (h - 1)
        coverage = hits / total if total else 0.0
        if coverage < self.min_coverage:
            return MarkerResult("NOT_FOUND", coverage, None, False, "no marker-coloured region")
        cy = sum_y / hits
        return MarkerResult("FOUND", coverage, cy, cy >= self.stop_line_y,
                            "marker low in frame" if cy >= self.stop_line_y else "marker visible but far")


# -------------------------------------------------------------------- recorded images
def read_ppm(path: str) -> list:
    """Read a binary (P6, maxval 255) PPM into ``rows[y][x] = (r, g, b)``."""
    with open(path, "rb") as f:
        data = f.read()
    tokens, pos = [], 0
    while len(tokens) < 4:
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        if data[pos:pos + 1] == b"#":
            while pos < len(data) and data[pos:pos + 1] != b"\n":
                pos += 1
            continue
        start = pos
        while pos < len(data) and not data[pos:pos + 1].isspace():
            pos += 1
        if start == pos:
            raise ValueError("truncated PPM header")
        tokens.append(data[start:pos])
    if tokens[0] != b"P6" or tokens[3] != b"255":
        raise ValueError("only binary P6 PPM with maxval 255 is supported")
    w, h = int(tokens[1]), int(tokens[2])
    pixels = data[pos + 1:]
    if len(pixels) < w * h * 3:
        raise ValueError("truncated PPM pixel data")
    return [[tuple(pixels[(y * w + x) * 3:(y * w + x) * 3 + 3]) for x in range(w)] for y in range(h)]


def write_ppm(path: str, frame: Sequence[Sequence[Pixel]]) -> None:
    h, w = len(frame), len(frame[0])
    with open(path, "wb") as f:
        f.write(f"P6\n{w} {h}\n255\n".encode())
        for row in frame:
            f.write(bytes(c for px in row for c in px))


def synthetic_frame(width: int = 160, height: int = 120, line_y: Optional[Tuple[int, int]] = None,
                    marker_rgb: Pixel = (200, 30, 30), floor_rgb: Pixel = (96, 96, 100)) -> list:
    """A flat grey 'floor' with an optional horizontal marker band between rows ``line_y``."""
    frame = [[floor_rgb for _ in range(width)] for _ in range(height)]
    if line_y:
        for y in range(line_y[0], line_y[1]):
            frame[y] = [marker_rgb for _ in range(width)]
    return frame
