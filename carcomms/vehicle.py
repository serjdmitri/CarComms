"""One vehicle as a real-time process talking UDP to its peer.

Motion is LOG-ONLY: the process prints WAIT / PROCEED but never touches a motor.
Run two of these (two terminals, or two Raspberry Pis) to see two independent
processes agree on a crossing order.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from typing import Callable, Optional

from .coordinator import Action, Coordinator, CoordinatorConfig, Event
from .messages import PHASE_CROSSING, PHASE_IDLE, MAX_PRIORITY, MOVEMENTS
from .network import UdpTransport, parse_endpoint
from .policy import get_policy
from .sensors import DistanceReading, classify_raw, read_safely

TICK_S = 0.05   # 20 Hz, the broadcast rate of the legacy prototype


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--id", required=True, help="unique vehicle id, e.g. car_a")
    p.add_argument("--listen", required=True, help="UDP endpoint to bind, e.g. 127.0.0.1:5005 or 0.0.0.0:5005")
    p.add_argument("--peer", required=True, help="the other vehicle's UDP endpoint, e.g. 127.0.0.1:5006")
    p.add_argument("--peer-id", default=None, help="expected id of the other vehicle (default: first one heard)")
    p.add_argument("--policy", default="priority", choices=["priority", "fcfs"])
    p.add_argument("--priority", type=int, default=0, help=f"0 (normal) to {MAX_PRIORITY} (most urgent)")
    p.add_argument("--movement", default="straight", choices=list(MOVEMENTS))
    p.add_argument("--arrive-after", type=float, default=1.0, help="seconds after start until reaching the stop line")
    p.add_argument("--cross-time", type=float, default=1.5, help="simulated seconds spent inside the intersection")
    p.add_argument("--trips", type=int, default=1, help="how many crossings to perform")
    p.add_argument("--sensor", default="sim", choices=["sim", "hcsr04"],
                   help="'sim' = fixed 100 cm reading; 'hcsr04' = the Raspberry Pi ultrasonic driver (UNTESTED)")
    p.add_argument("--sensor-fault-until", type=float, default=0.0,
                   help="(sim sensor) return an invalid reading until this many seconds after start")
    p.add_argument("--t0", type=float, default=None, help="shared start time (time.monotonic) for aligned logs")
    p.add_argument("--timeout", type=float, default=60.0, help="give up after this many seconds")
    p.add_argument("--linger", type=float, default=3.0, help="keep broadcasting this long after the last crossing")


def _make_sensor(args) -> Callable[[float], DistanceReading]:
    if args.sensor == "hcsr04":
        from .hardware import hcsr04_reader
        read_cm = hcsr04_reader()
        return lambda t: read_safely(read_cm, t)
    return lambda t: classify_raw(None if t < args.sensor_fault_until else 100.0, t)


def run(args: argparse.Namespace) -> int:
    t0 = args.t0 if args.t0 is not None else time.monotonic()
    printed = {"last_action": None}

    def log(ev: Event) -> None:
        print(str(ev), flush=True)

    config = CoordinatorConfig(broadcast_interval_s=TICK_S)
    coord = Coordinator(args.id, get_policy(args.policy), config, peer_id=args.peer_id, log=log)
    transport = UdpTransport(parse_endpoint(args.listen, "127.0.0.1"), parse_endpoint(args.peer, "127.0.0.1"))
    sensor = _make_sensor(args)

    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("flag", True))

    trips_done = 0
    next_arrival: Optional[float] = args.arrive_after
    arrival_t = enter_t = None
    finished_at: Optional[float] = None
    waits = []
    print(f"[{args.id}] start policy={args.policy} priority={args.priority} listen={args.listen} "
          f"peer={args.peer} MOTORS=OFF (log only)", flush=True)

    try:
        while not stop["flag"]:
            loop_start = time.monotonic()
            t = loop_start - t0
            for data in transport.poll():
                coord.on_datagram(t, data)

            if coord.phase == PHASE_CROSSING and enter_t is not None and t - enter_t >= args.cross_time:
                coord.exit_intersection(t)
                trips_done += 1
                enter_t = None
                next_arrival = t if trips_done < args.trips else None
                if trips_done >= args.trips:
                    finished_at = t
            if coord.phase == PHASE_IDLE and next_arrival is not None and t >= next_arrival:
                coord.request_crossing(t, args.priority, args.movement)
                arrival_t, next_arrival = t, None

            out = coord.tick(t, sensor(t))
            for m in out.messages:
                transport.send(m.encode())
            if coord.phase == PHASE_CROSSING and enter_t is None:
                enter_t = t
                waits.append(t - (arrival_t or t))
            if out.action != printed["last_action"]:
                printed["last_action"] = out.action
                print(f"t={t:7.3f}  {args.id:<6} MOTION(log-only) {out.action.value}"
                      + (f"  ({out.reason})" if out.reason else ""), flush=True)

            if finished_at is not None and t - finished_at >= args.linger:
                break
            if t > args.timeout:
                print(f"[{args.id}] TIMEOUT after {args.timeout:.0f}s: still {coord.phase}; "
                      f"holding is the safe default", flush=True)
                return 2
            time.sleep(max(0.0, TICK_S - (time.monotonic() - loop_start)))
    finally:
        transport.close()

    mean = sum(waits) / len(waits) if waits else float("nan")
    print(f"[{args.id}] DONE trips={trips_done} mean_wait={mean:.3f}s counters={dict(coord.counters)}", flush=True)
    return 0 if trips_done >= args.trips else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_arguments(p)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
