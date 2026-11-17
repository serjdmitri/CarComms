"""Two-vehicle intersection coordinator (no I/O, no clocks, no hardware).

Design
------
Each vehicle owns a small state machine, ``IDLE -> REQUESTING -> CROSSING ->
IDLE``, and broadcasts its full state (see ``messages.StateMessage``). A
vehicle may **enter only while it holds a grant from its peer** for its
current request. A grant is a field in the granter's own state ("I grant your
request number n") and stays set until the grantee reports that request
released. The rules for giving a grant use only the granter's own state plus
the peer's latest request:

* granter ``CROSSING``                         -> never grant
* granter ``REQUESTING`` and *holds the peer's grant*
                                               -> never grant (committed)
* granter ``REQUESTING`` otherwise             -> grant only if the peer's
                                                  request sorts first under the policy
* granter ``IDLE``                             -> grant

A vehicle that has granted the peer cannot enter until that grant is
released. Together these give exclusive access for two vehicles:

* Both entering would need grant(A->B) and grant(B->A) outstanding at once.
  Entering requires *no* outstanding grant of your own, so each would have
  to have its own grant cleared, which only happens after the peer released,
  i.e. after the peer left the intersection.
* Duplicated, delayed or re-ordered messages cannot undo this, because the
  safety-relevant fields (``req``, ``released``, ``grant``) only move
  forward, and a vehicle acts only on the newest message (older sequence
  numbers are dropped).
* Silence never grants anything. A timeout can only make a vehicle *more*
  conservative: it will not enter while the link is down, and it never
  treats "no message" as "intersection empty".

Assumptions (see README "Known limitations"): exactly two cooperating
vehicles, a single conflict zone, no message authentication, no
mid-crossing reboot, and both vehicles run the same policy.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Counter as CounterT, List, Optional

from .messages import (MessageError, PHASE_CROSSING, PHASE_IDLE, PHASE_REQUESTING,
                       MOVEMENTS, MAX_PRIORITY, StateMessage, decode)
from .policy import Policy, PriorityPolicy, RequestView
from .sensors import DistanceReading, path_clear


class Action(Enum):
    FREE = "FREE"          # no request pending; vehicle is not using the coordinator
    WAIT = "WAIT"          # hold at the stop line
    PROCEED = "PROCEED"    # cross now (it holds a grant and has entered)


@dataclass(frozen=True)
class Event:
    time: float
    vehicle: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"t={self.time:7.3f}  {self.vehicle:<6} {self.kind:<14} {self.detail}"


@dataclass
class CoordinatorConfig:
    link_timeout_s: float = 0.5        # peer silent longer than this => link considered down
    broadcast_interval_s: float = 0.05  # 20 Hz, same rate as the legacy prototype
    clear_dist_cm: float = 30.0        # same value as the legacy SAFE_DIST_CM
    sensor_max_age_s: float = 0.5
    require_sensor: bool = True        # no valid "path clear" reading => do not enter
    no_echo_is_clear: bool = False     # legacy 999 "no echo" is ambiguous; off by default


@dataclass
class TickOutput:
    messages: List[StateMessage]
    action: Action
    reason: str


class Coordinator:
    def __init__(self, vehicle_id: str, policy: Optional[Policy] = None,
                 config: Optional[CoordinatorConfig] = None, peer_id: Optional[str] = None,
                 log: Optional[Callable[[Event], None]] = None, boot_id: Optional[int] = None) -> None:
        if not vehicle_id:
            raise ValueError("vehicle_id must be non-empty")
        self.vid = vehicle_id
        self.policy = policy or PriorityPolicy()
        self.config = config or CoordinatorConfig()
        self.peer_id = peer_id
        self._log = log
        self.boot = boot_id if boot_id is not None else random.getrandbits(31)
        self._restart_pending = False

        self.phase = PHASE_IDLE
        self.req = 0            # own request counter
        self.req_ts = 0         # Lamport timestamp of own current request
        self.released = 0       # highest own request that finished
        self.priority = 0
        self.movement = "straight"
        self.clock = 0          # Lamport clock
        self.grant = 0          # peer request number we currently grant (0 = none)

        self.peer: Optional[StateMessage] = None
        self.last_rx: Optional[float] = None
        self.fault: Optional[str] = None   # latched; blocks entering and granting until cleared

        self._seq = 0
        self._last_tx: Optional[float] = None
        self._dirty = True
        self._link_up: Optional[bool] = None
        self._reason = ""
        self.events: List[Event] = []
        self.counters: CounterT[str] = Counter()

    # ------------------------------------------------------------------ helpers
    def _emit(self, now: float, kind: str, detail: str = "") -> None:
        ev = Event(now, self.vid, kind, detail)
        self.events.append(ev)
        if self._log:
            self._log(ev)

    def link_alive(self, now: float) -> bool:
        return self.last_rx is not None and (now - self.last_rx) <= self.config.link_timeout_s

    def _peer_pending(self) -> bool:
        p = self.peer
        return p is not None and p.req > p.released

    # ------------------------------------------------------------------ inputs
    def request_crossing(self, now: float, priority: int = 0, movement: str = "straight") -> bool:
        """The vehicle reached its stop line and wants to cross."""
        if self.phase != PHASE_IDLE:
            self._emit(now, "REQUEST_IGNORED", f"already {self.phase}")
            return False
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= MAX_PRIORITY:
            raise ValueError(f"priority must be an integer 0..{MAX_PRIORITY}")
        if movement not in MOVEMENTS:
            raise ValueError(f"movement must be one of {MOVEMENTS}")
        self.clock += 1
        self.req += 1
        self.req_ts = self.clock
        self.priority = priority
        self.movement = movement
        self.phase = PHASE_REQUESTING
        self._dirty = True
        self._emit(now, "REQUEST", f"#{self.req} priority={priority} movement={movement} ts={self.req_ts}")
        self._grant_step(now)
        return True

    def exit_intersection(self, now: float) -> bool:
        """The vehicle has fully cleared the intersection: release it."""
        if self.phase != PHASE_CROSSING:
            self._emit(now, "EXIT_IGNORED", f"phase is {self.phase}")
            return False
        self.phase = PHASE_IDLE
        self.released = self.req
        self._dirty = True
        self._emit(now, "EXIT", f"#{self.req}")
        self._emit(now, "RELEASE", f"#{self.req}")
        self._grant_step(now)   # a request that was deferred while we crossed is granted now
        return True

    def cancel_request(self, now: float) -> bool:
        """Withdraw a request before entering. Treated as an immediate release."""
        if self.phase != PHASE_REQUESTING:
            return False
        self.phase = PHASE_IDLE
        self.released = self.req
        self._dirty = True
        self._emit(now, "CANCEL", f"#{self.req}")
        self._grant_step(now)
        return True

    def clear_fault(self, now: float) -> None:
        """Operator action: acknowledge a fault. Only call this once the intersection is
        known to be empty. After a peer restart it also forgets the grant we gave the
        old incarnation of the peer."""
        if self.fault:
            self._emit(now, "FAULT_CLEARED", self.fault)
            self.fault = None
            if self._restart_pending:
                self._restart_pending = False
                self.grant = 0
                self._dirty = True

    def on_datagram(self, now: float, payload: bytes) -> bool:
        try:
            msg = decode(payload)
        except MessageError as exc:
            self.counters["dropped_invalid"] += 1
            self._emit(now, "DROP_INVALID", str(exc))
            return False
        return self.on_message(now, msg)

    def on_message(self, now: float, msg: StateMessage) -> bool:
        """Process one peer state message. Returns True if it was accepted."""
        if msg.sender == self.vid:
            self.counters["ignored_self_echo"] += 1   # broadcast loop-back
            return False
        if self.peer_id is None:
            self.peer_id = msg.sender
            self._emit(now, "PEER_FOUND", msg.sender)
        elif msg.sender != self.peer_id:
            self.counters["dropped_unknown_sender"] += 1
            self._emit(now, "DROP_SENDER", f"{msg.sender} is not peer {self.peer_id}")
            return False

        if self.peer is not None and msg.boot != self.peer.boot:
            # The peer rebooted: its sequence numbers and request numbers start over, and
            # we cannot know whether it was inside the intersection when it died.
            self.counters["peer_restarts"] += 1
            self._restart_pending = True
            self._set_fault(now, "peer restarted (new boot id): its state is unknown, holding until an "
                                 "operator confirms the intersection is empty")
            self.peer = None
        if self.peer is not None:
            if msg.seq == self.peer.seq:
                self.counters["dropped_duplicate"] += 1
                self._emit(now, "DROP_DUPLICATE", f"seq={msg.seq}")
                return False
            if msg.seq < self.peer.seq:
                self.counters["dropped_stale"] += 1
                self._emit(now, "DROP_STALE", f"seq={msg.seq} < {self.peer.seq}")
                return False
            # Monotonic fields must never go backwards while sequence numbers go forwards.
            if msg.req < self.peer.req or msg.released < self.peer.released:
                self._set_fault(now, "peer state went backwards (peer restarted?); holding until cleared")

        if msg.policy != self.policy.name:
            self._set_fault(now, f"policy mismatch: peer runs '{msg.policy}', we run '{self.policy.name}'")

        self.peer = msg
        self.last_rx = now
        self.clock = max(self.clock, msg.clock)
        self._check_conflict(now)
        self._grant_step(now)
        return True

    # ------------------------------------------------------------------ rules
    def _set_fault(self, now: float, why: str) -> None:
        if self.fault != why:
            self.fault = why
            self._emit(now, "FAULT", why)

    def _check_conflict(self, now: float) -> None:
        """Detect a peer that entered without our grant (protocol violation)."""
        p = self.peer
        if p is None or p.phase != PHASE_CROSSING:
            return
        if self.grant != p.req:
            self._set_fault(now, f"peer is CROSSING #{p.req} without our grant")
        if self.phase == PHASE_CROSSING:
            self._set_fault(now, "both vehicles report CROSSING")

    def _grant_step(self, now: float) -> None:
        p = self.peer
        # Release our outstanding grant once the peer reports that request finished.
        if self.grant and p is not None and p.released >= self.grant:
            self._emit(now, "GRANT_RELEASED", f"peer #{self.grant} finished")
            self.grant = 0
            self._dirty = True
        if self.grant or self.fault or not self._peer_pending():
            return
        assert p is not None
        if self.phase == PHASE_CROSSING:
            return
        if self.phase == PHASE_REQUESTING:
            if p.grant == self.req:
                return  # the peer already granted us: we are committed and the peer must wait
            mine = RequestView(self.vid, self.priority, self.req_ts, self.req)
            theirs = RequestView(p.sender, p.priority, p.req_ts, p.req)
            if self.policy.key(mine) < self.policy.key(theirs):
                return  # our request sorts first: defer the peer
            why = f"yield to {p.sender} (priority {p.priority} vs {self.priority})"
        else:
            why = "idle"
        self.grant = p.req
        self._dirty = True
        self._emit(now, "GRANT_GIVEN", f"to {p.sender} #{p.req}: {why}")

    def _entry_step(self, now: float, sensor: Optional[DistanceReading]) -> None:
        if self.phase != PHASE_REQUESTING:
            self._reason = ""
            return
        p = self.peer
        reason = ""
        if self.fault:
            reason = f"fault: {self.fault}"
        elif p is None or p.grant != self.req:
            if self.grant:
                reason = f"yielding to {self.peer_id} (granted #{self.grant})"
            elif not self.link_alive(now):
                reason = "waiting for grant (peer silent)"
            else:
                reason = f"waiting for grant from {self.peer_id}"
        elif self.grant:
            reason = f"yielding to {self.peer_id} (granted #{self.grant})"
        elif not self.link_alive(now):
            reason = "hold: link down, will not treat silence as an empty intersection"
        else:
            ok, why = (True, "sensor not required")
            if self.config.require_sensor:
                ok, why = path_clear(sensor, now, clear_cm=self.config.clear_dist_cm,
                                     max_age_s=self.config.sensor_max_age_s,
                                     no_echo_is_clear=self.config.no_echo_is_clear)
            if not ok:
                reason = f"hold: {why}"
            else:
                self.phase = PHASE_CROSSING
                self._dirty = True
                self._emit(now, "ENTER", f"#{self.req} ({why})")
                self._reason = "crossing"
                return
        if reason != self._reason:
            self._reason = reason
            self._emit(now, "HOLD", reason)

    # ------------------------------------------------------------------ output
    def tick(self, now: float, sensor: Optional[DistanceReading] = None) -> TickOutput:
        """Advance the state machine and return datagrams to send plus the drive action."""
        up = self.link_alive(now)
        if self.peer is not None and self._link_up is not up:
            if self._link_up is not None:
                self._emit(now, "LINK_UP" if up else "LINK_DOWN",
                           "" if up else f"no message for > {self.config.link_timeout_s}s")
            self._link_up = up
        elif self.peer is None:
            self._link_up = False

        self._grant_step(now)
        self._entry_step(now, sensor)

        out: List[StateMessage] = []
        due = self._last_tx is None or (now - self._last_tx) >= self.config.broadcast_interval_s
        if due or self._dirty:
            self._seq += 1
            out.append(StateMessage(
                sender=self.vid, seq=self._seq, policy=self.policy.name, phase=self.phase,
                req=self.req, priority=self.priority, movement=self.movement,
                clock=self.clock, req_ts=self.req_ts, grant=self.grant,
                released=self.released, sent_at=now, boot=self.boot))
            self._last_tx = now
            self._dirty = False

        if self.phase == PHASE_CROSSING:
            action, reason = Action.PROCEED, "crossing"
        elif self.phase == PHASE_REQUESTING:
            action, reason = Action.WAIT, self._reason or "waiting"
        else:
            action, reason = Action.FREE, ""
        return TickOutput(out, action, reason)
