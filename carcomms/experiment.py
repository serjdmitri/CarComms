"""Reproducible simulation experiment: first-come-first-served vs priority-aware.

Everything here is a *simulation* of the coordination protocol with a fixed
crossing time and a modelled network. It says nothing about real cars,
real radios or destination-level travel time. Same arrival scenarios are fed
to both policies, and the numbers in the README come from this script.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .network import SimNetwork
from .simulation import SimResult, Trip, run_simulation

LATENCY_S = 0.05      # modelled one-way message delay
CROSSING_S = 1.5      # modelled time a vehicle spends inside the intersection
PRIORITY = 5          # priority level given to the "priority" vehicle in every scenario


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    trips: Sequence[Trip]
    priority_vehicle: str


def named_scenarios() -> List[Scenario]:
    def t(vehicle, at=None, gap=None, prio=0):
        return Trip(vehicle, arrive_at=at, gap_after_previous=gap, priority=prio, crossing_time=CROSSING_S)

    return [
        Scenario("S1a simultaneous, car_a has priority", "both reach the stop line at t=1.00",
                 [t("car_a", 1.0, prio=PRIORITY), t("car_b", 1.0)], "car_a"),
        Scenario("S1b simultaneous, car_b has priority", "both reach the stop line at t=1.00",
                 [t("car_a", 1.0), t("car_b", 1.0, prio=PRIORITY)], "car_b"),
        Scenario("S2 equal priority, simultaneous", "same arrival, nobody has priority (car_b is 'priority' only for reporting)",
                 [t("car_a", 1.0), t("car_b", 1.0)], "car_b"),
        Scenario("S3 priority arrives 0.05 s after other", "inside the message-latency window",
                 [t("car_a", 1.0), t("car_b", 1.05, prio=PRIORITY)], "car_b"),
        Scenario("S4 priority arrives 0.50 s after other", "the other car is already crossing",
                 [t("car_a", 1.0), t("car_b", 1.5, prio=PRIORITY)], "car_b"),
        Scenario("S5 priority car repeats 3 trips", "car_b (priority) re-requests immediately after each exit; car_a arrives at t=1.0",
                 [t("car_b", 0.5, prio=PRIORITY), t("car_b", gap=0.0, prio=PRIORITY),
                  t("car_b", gap=0.0, prio=PRIORITY), t("car_a", 1.0)], "car_b"),
    ]


def _network(seed: int, latency: float = LATENCY_S, loss: float = 0.0, jitter: float = 0.0) -> SimNetwork:
    return SimNetwork(seed=seed, latency_s=latency, loss=loss, jitter_s=jitter)


def _summarise(res: SimResult, priority_vehicle: str) -> Dict[str, float]:
    other = "car_a" if priority_vehicle == "car_b" else "car_b"
    wp = sum(res.waits(priority_vehicle))
    wo = sum(res.waits(other))
    return {"priority_wait": wp, "other_wait": wo, "total_wait": wp + wo,
            "first": res.enter_order()[0] if res.enter_order() else "",
            "overlaps": res.overlaps(), "completed": res.all_completed}


def run_named(seed: int = 1) -> List[Dict]:
    rows = []
    for sc in named_scenarios():
        row = {"scenario": sc.name, "description": sc.description, "priority_vehicle": sc.priority_vehicle}
        for pol in ("fcfs", "priority"):
            res = run_simulation(sc.trips, policy=pol, network=_network(seed))
            row[pol] = _summarise(res, sc.priority_vehicle)
        rows.append(row)
    return rows


def random_arrivals(n: int = 2000, seed: int = 1, window_s: float = 4.0, latency: float = LATENCY_S,
                    loss: float = 0.0) -> Dict:
    """Both vehicles arrive at uniformly random times in [0, window_s]; which one has priority is random."""
    rng = random.Random(seed)
    acc = {pol: {"priority_wait": 0.0, "other_wait": 0.0, "total_wait": 0.0, "priority_first": 0}
           for pol in ("fcfs", "priority")}
    differ = 0
    overlaps = 0
    unfinished = 0
    contested = 0
    for i in range(n):
        a_at, b_at = rng.uniform(0, window_s), rng.uniform(0, window_s)
        pv = rng.choice(["car_a", "car_b"])
        trips = [Trip("car_a", arrive_at=a_at, priority=PRIORITY if pv == "car_a" else 0, crossing_time=CROSSING_S),
                 Trip("car_b", arrive_at=b_at, priority=PRIORITY if pv == "car_b" else 0, crossing_time=CROSSING_S)]
        firsts = {}
        for pol in ("fcfs", "priority"):
            res = run_simulation(trips, policy=pol, network=_network(seed * 100003 + i, latency, loss))
            s = _summarise(res, pv)
            overlaps += s["overlaps"]
            unfinished += 0 if s["completed"] else 1
            for k in ("priority_wait", "other_wait", "total_wait"):
                acc[pol][k] += s[k]
            acc[pol]["priority_first"] += 1 if s["first"] == pv else 0
            firsts[pol] = s["first"]
        differ += firsts["fcfs"] != firsts["priority"]
        contested += abs(a_at - b_at) <= latency + 0.05
    out = {"trials": n, "window_s": window_s, "latency_s": latency, "loss": loss,
           "order_differs": differ / n, "contested_arrivals": contested / n,
           "overlaps": overlaps, "unfinished": unfinished}
    for pol in acc:
        out[pol] = {k: (v / n) for k, v in acc[pol].items()}
    return out


def latency_sweep(n: int = 1000, seed: int = 1, latencies: Sequence[float] = (0.02, 0.05, 0.1, 0.2)) -> List[Dict]:
    return [random_arrivals(n=n, seed=seed, latency=l) for l in latencies]


def run_all(seed: int = 1, n: int = 2000) -> Dict:
    return {
        "model": {"latency_s": LATENCY_S, "crossing_s": CROSSING_S, "priority_level": PRIORITY,
                  "dt_s": 0.05, "seed": seed},
        "named": run_named(seed),
        "random_arrivals": random_arrivals(n=n, seed=seed),
        "random_arrivals_10pct_loss": random_arrivals(n=n // 2, seed=seed, loss=0.10),
        "latency_sweep": latency_sweep(n=n // 2, seed=seed),
    }


def render_markdown(data: Dict) -> str:
    m = data["model"]
    L: List[str] = []
    L.append("# Simulation results: first-come-first-served vs priority-aware")
    L.append("")
    L.append("**These are simulation results**, produced by `python3 -m carcomms experiment`. "
             f"Model: one intersection, two cars, {m['crossing_s']} s inside the intersection, "
             f"{m['latency_s'] * 1000:.0f} ms one-way message delay, 20 Hz state broadcasts, seed {m['seed']}. "
             "No hardware was involved. Waiting time = from reaching the stop line to entering the intersection.")
    L.append("")
    L.append("## Named scenarios (same arrivals for both policies)")
    L.append("")
    L.append("| Scenario | Policy | Priority car wait (s) | Other car wait (s) | Total wait (s) | Went first |")
    L.append("|---|---|---:|---:|---:|---|")
    for r in data["named"]:
        for pol, label in (("fcfs", "FCFS"), ("priority", "Priority")):
            s = r[pol]
            L.append(f"| {r['scenario']} | {label} | {s['priority_wait']:.2f} | {s['other_wait']:.2f} | "
                     f"{s['total_wait']:.2f} | {s['first']} |")
    L.append("")
    ra = data["random_arrivals"]
    L.append(f"## Random arrivals ({ra['trials']} trials, both cars arrive uniformly within {ra['window_s']:.0f} s)")
    L.append("")
    L.append("| Policy | Priority car mean wait (s) | Other car mean wait (s) | Total mean wait (s) | Priority car went first |")
    L.append("|---|---:|---:|---:|---:|")
    for pol, label in (("fcfs", "FCFS"), ("priority", "Priority")):
        s = ra[pol]
        L.append(f"| {label} | {s['priority_wait']:.3f} | {s['other_wait']:.3f} | {s['total_wait']:.3f} | "
                 f"{s['priority_first'] * 100:.1f}% |")
    L.append("")
    L.append(f"The two policies chose a different crossing order in {ra['order_differs'] * 100:.1f}% of trials; "
             f"{ra['contested_arrivals'] * 100:.1f}% of trials had arrivals within {(ra['latency_s'] + 0.05) * 1000:.0f} ms "
             f"of each other. Overlaps in the intersection: {ra['overlaps']}. Trials that did not finish: {ra['unfinished']}.")
    L.append("")
    rl = data["random_arrivals_10pct_loss"]
    L.append(f"## Same, with 10% of messages lost ({rl['trials']} trials)")
    L.append("")
    L.append("| Policy | Priority car mean wait (s) | Other car mean wait (s) | Total mean wait (s) |")
    L.append("|---|---:|---:|---:|")
    for pol, label in (("fcfs", "FCFS"), ("priority", "Priority")):
        s = rl[pol]
        L.append(f"| {label} | {s['priority_wait']:.3f} | {s['other_wait']:.3f} | {s['total_wait']:.3f} |")
    L.append("")
    L.append(f"Overlaps: {rl['overlaps']}. Trials that did not finish: {rl['unfinished']}.")
    L.append("")
    L.append("## Sensitivity to message delay")
    L.append("")
    L.append("| One-way delay | Order differs | Priority car mean wait, FCFS (s) | Priority car mean wait, Priority (s) | Other car mean wait, FCFS (s) | Other car mean wait, Priority (s) |")
    L.append("|---:|---:|---:|---:|---:|---:|")
    for r in data["latency_sweep"]:
        L.append(f"| {r['latency_s'] * 1000:.0f} ms | {r['order_differs'] * 100:.1f}% | {r['fcfs']['priority_wait']:.3f} | "
                 f"{r['priority']['priority_wait']:.3f} | {r['fcfs']['other_wait']:.3f} | {r['priority']['other_wait']:.3f} |")
    L.append("")
    return "\n".join(L)


def main(out_prefix: Optional[str] = None, seed: int = 1, n: int = 2000) -> str:
    data = run_all(seed=seed, n=n)
    md = render_markdown(data)
    if out_prefix:
        with open(out_prefix + ".md", "w", encoding="utf-8") as f:
            f.write(md + "\n")
        with open(out_prefix + ".json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
    return md
