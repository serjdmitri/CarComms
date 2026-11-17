"""Deterministic two-vehicle intersection simulation (no motors, no wall clock).

Time advances in fixed steps. Each vehicle has a list of trips; a trip is
"arrive at the stop line, request, wait for a grant, cross for a fixed time,
release". The simulator measures waiting time from the moment a vehicle
*arrives* to the moment it *enters*, and independently checks the safety
invariant (never both inside the intersection) from the recorded enter/exit
intervals of the trips, not from what either coordinator believes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Union

from .coordinator import Coordinator, CoordinatorConfig, Event
from .messages import PHASE_CROSSING
from .network import SimNetwork
from .policy import get_policy
from .sensors import DistanceReading, classify_raw

SensorFn = Callable[[float], object]   # time -> raw reading (number, None, 999, ...)


@dataclass(frozen=True)
class Trip:
    vehicle: str
    arrive_at: Optional[float] = None            # absolute time reaching the stop line
    gap_after_previous: Optional[float] = None   # or: seconds after the previous trip's exit
    priority: int = 0
    movement: str = "straight"
    crossing_time: float = 1.5                   # seconds spent inside the intersection

    def __post_init__(self) -> None:
        if (self.arrive_at is None) == (self.gap_after_previous is None):
            raise ValueError("give exactly one of arrive_at / gap_after_previous")


@dataclass
class TripResult:
    vehicle: str
    priority: int
    arrive: float
    enter: Optional[float] = None
    exit: Optional[float] = None

    @property
    def completed(self) -> bool:
        return self.exit is not None

    def wait(self, horizon: float) -> float:
        """Time between arriving and entering (censored at ``horizon`` if it never entered)."""
        return (self.enter if self.enter is not None else horizon) - self.arrive


@dataclass
class SimResult:
    policy: str
    trips: List[TripResult]
    events: List[Event]
    conflict_ticks: int   # ticks in which both coordinators reported CROSSING
    duration: float
    network: SimNetwork
    counters: Dict[str, Dict[str, int]] = field(default_factory=dict)

    @property
    def all_completed(self) -> bool:
        return all(t.completed for t in self.trips)

    def waits(self, vehicle: Optional[str] = None) -> List[float]:
        return [t.wait(self.duration) for t in self.trips if vehicle in (None, t.vehicle)]

    def overlaps(self) -> int:
        """Number of trip pairs whose [enter, exit) intervals overlap in time (must be 0).

        A trip that entered but never exited counts as occupying the intersection forever."""
        spans = [(t.enter, t.exit if t.exit is not None else float("inf"), t.vehicle)
                 for t in self.trips if t.enter is not None]
        n = 0
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                a, b = spans[i], spans[j]
                if a[2] != b[2] and a[0] < b[1] and b[0] < a[1]:
                    n += 1
        return n

    def enter_order(self) -> List[str]:
        done = [t for t in self.trips if t.enter is not None]
        return [t.vehicle for t in sorted(done, key=lambda t: (t.enter, t.vehicle))]


class _SimVehicle:
    def __init__(self, vid: str, peer: str, trips: Sequence[Trip], policy_name: str,
                 config: CoordinatorConfig, sensor: Optional[SensorFn],
                 log: Optional[Callable[[Event], None]]) -> None:
        self.vid = vid
        self.peer = peer
        self.coord = Coordinator(vid, get_policy(policy_name), config, peer_id=peer, log=log)
        self.sensor = sensor
        self.queue = list(trips)
        self.current: Optional[Trip] = None
        self.result: Optional[TripResult] = None
        self.results: List[TripResult] = []
        self.next_arrival: Optional[float] = None
        self._schedule_next(None)

    def _schedule_next(self, prev_exit: Optional[float]) -> None:
        if not self.queue:
            self.next_arrival = None
            return
        trip = self.queue[0]
        if trip.arrive_at is not None:
            self.next_arrival = trip.arrive_at if prev_exit is None else max(trip.arrive_at, prev_exit)
        else:
            self.next_arrival = (prev_exit or 0.0) + float(trip.gap_after_previous or 0.0)

    @property
    def done(self) -> bool:
        return not self.queue and self.current is None

    def reading(self, now: float) -> DistanceReading:
        raw = self.sensor(now) if self.sensor else 100.0
        return raw if isinstance(raw, DistanceReading) else classify_raw(raw, now)


def run_simulation(trips: Sequence[Trip], *, policy: str = "priority",
                   network: Optional[SimNetwork] = None, dt: float = 0.05,
                   max_time: float = 60.0, config: Optional[CoordinatorConfig] = None,
                   sensors: Optional[Dict[str, SensorFn]] = None,
                   log: Optional[Callable[[Event], None]] = None) -> SimResult:
    """Run all trips of two vehicles through one intersection."""
    ids = sorted({t.vehicle for t in trips})
    if len(ids) != 2:
        raise ValueError(f"exactly two vehicles are supported, got {ids}")
    network = network or SimNetwork(latency_s=0.05)
    config = config or CoordinatorConfig(broadcast_interval_s=dt)
    sensors = sensors or {}
    vehicles = {
        vid: _SimVehicle(vid, [x for x in ids if x != vid][0],
                         [t for t in trips if t.vehicle == vid], policy, config,
                         sensors.get(vid), log)
        for vid in ids
    }

    conflict_ticks = 0
    step = 0
    now = 0.0
    while now <= max_time:
        now = round(step * dt, 6)
        for dst, payload in network.deliver(now):
            vehicles[dst].coord.on_datagram(now, payload)

        for vid in ids:
            v = vehicles[vid]
            c = v.coord
            # finish crossing
            if v.result is not None and v.result.enter is not None and v.result.exit is None:
                if now - v.result.enter >= v.current.crossing_time - 1e-9:
                    c.exit_intersection(now)
                    v.result.exit = now
                    v.current = None
                    v.result = None
                    v.queue.pop(0)
                    v._schedule_next(now)
            # arrive at stop line
            if v.current is None and v.next_arrival is not None and now >= v.next_arrival - 1e-9:
                trip = v.queue[0]
                v.current = trip
                v.result = TripResult(vid, trip.priority, now)
                v.results.append(v.result)
                c.request_crossing(now, trip.priority, trip.movement)
            out = c.tick(now, v.reading(now))
            if v.result is not None and v.result.enter is None and c.phase == PHASE_CROSSING:
                v.result.enter = now
            for msg in out.messages:
                network.send(now, v.peer, msg.encode())

        if all(v.coord.phase == PHASE_CROSSING for v in vehicles.values()):
            conflict_ticks += 1
        if all(v.done for v in vehicles.values()):
            break
        step += 1

    events: List[Event] = sorted((e for v in vehicles.values() for e in v.coord.events),
                                 key=lambda e: (e.time, e.vehicle))
    results = [r for vid in ids for r in vehicles[vid].results]
    return SimResult(
        policy=policy, trips=results, events=events, conflict_ticks=conflict_ticks,
        duration=now, network=network,
        counters={vid: dict(vehicles[vid].coord.counters) for vid in ids})
