"""Wire format for vehicle-to-vehicle intersection coordination.

Each vehicle periodically broadcasts its *complete* coordination state in one
small JSON datagram. Because every message is the full, latest state (not a
delta), a lost message is repaired by the next one, and duplicated or
re-ordered messages are harmless: every safety-relevant field is monotonic
(see ``Coordinator`` for the argument).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from typing import Any, Dict

PROTOCOL_VERSION = 1

PHASE_IDLE = "IDLE"
PHASE_REQUESTING = "REQUESTING"
PHASE_CROSSING = "CROSSING"
PHASES = (PHASE_IDLE, PHASE_REQUESTING, PHASE_CROSSING)

MOVEMENTS = ("straight", "left", "right")

MAX_PRIORITY = 9
MAX_DATAGRAM_BYTES = 1024
MAX_ID_LEN = 32


class MessageError(ValueError):
    """Raised when a datagram is not a valid CarComms state message."""


@dataclass(frozen=True)
class StateMessage:
    """Full coordination state of one vehicle at the moment it was sent."""

    sender: str      # unique vehicle id
    seq: int         # per-sender datagram counter, strictly increasing
    policy: str      # policy name; both vehicles must run the same one
    phase: str       # IDLE | REQUESTING | CROSSING
    req: int         # number of this sender's latest request (0 = none yet)
    priority: int    # priority of request ``req`` (0 = normal, higher = more urgent)
    movement: str    # intended movement of request ``req``
    clock: int       # sender's Lamport clock when the datagram was built
    req_ts: int      # Lamport timestamp of request ``req``
    grant: int       # peer request number this sender currently grants (0 = none)
    released: int    # highest own request number that has finished
    sent_at: float   # sender's own clock; diagnostics only, never used for decisions
    boot: int = 0    # random id chosen when the sender's coordinator started; changes on reboot
    version: int = PROTOCOL_VERSION

    def encode(self) -> bytes:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True).encode("utf-8")


def _int_field(data: Dict[str, Any], name: str, lo: int = 0, hi: int = 2**31) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise MessageError(f"field '{name}' must be an integer")
    if value < lo or value > hi:
        raise MessageError(f"field '{name}' out of range: {value}")
    return value


def _str_field(data: Dict[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value or len(value) > MAX_ID_LEN:
        raise MessageError(f"field '{name}' must be a non-empty string up to {MAX_ID_LEN} chars")
    return value


def decode(payload: bytes) -> StateMessage:
    """Parse and validate a datagram. Raises ``MessageError`` on anything odd."""
    if not isinstance(payload, (bytes, bytearray)):
        raise MessageError("payload must be bytes")
    if len(payload) > MAX_DATAGRAM_BYTES:
        raise MessageError("datagram too large")
    try:
        data = json.loads(bytes(payload).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise MessageError(f"not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MessageError("top-level JSON value must be an object")

    version = _int_field(data, "version", 1, 1_000)
    if version != PROTOCOL_VERSION:
        raise MessageError(f"unsupported protocol version {version}")

    phase = data.get("phase")
    if phase not in PHASES:
        raise MessageError(f"unknown phase {phase!r}")
    movement = data.get("movement")
    if movement not in MOVEMENTS:
        raise MessageError(f"unknown movement {movement!r}")

    sent_at = data.get("sent_at")
    if isinstance(sent_at, bool) or not isinstance(sent_at, (int, float)) or not math.isfinite(sent_at):
        raise MessageError("field 'sent_at' must be a finite number")

    msg = StateMessage(
        sender=_str_field(data, "sender"),
        seq=_int_field(data, "seq", 0),
        policy=_str_field(data, "policy"),
        phase=phase,
        req=_int_field(data, "req"),
        priority=_int_field(data, "priority", 0, MAX_PRIORITY),
        movement=movement,
        clock=_int_field(data, "clock"),
        req_ts=_int_field(data, "req_ts"),
        grant=_int_field(data, "grant"),
        released=_int_field(data, "released"),
        sent_at=float(sent_at),
        boot=_int_field(data, "boot"),
        version=version,
    )
    if msg.released > msg.req:
        raise MessageError("'released' cannot exceed 'req'")
    if msg.phase == PHASE_IDLE and msg.released != msg.req:
        raise MessageError("IDLE requires released == req")
    if msg.phase != PHASE_IDLE and msg.released >= msg.req:
        raise MessageError(f"{msg.phase} requires an unreleased request")
    return msg
