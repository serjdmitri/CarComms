"""Command-line entry point: ``python3 -m carcomms <command>``."""

from __future__ import annotations

import argparse
import glob
import os
import sys

from . import demo, experiment, perception, vehicle
from .network import SimNetwork
from .plot import timeline_svg
from .simulation import Trip, run_simulation


def _simulate(a: argparse.Namespace) -> int:
    net = SimNetwork(seed=a.seed, latency_s=a.latency, loss=a.loss, duplicate=a.duplicate)
    trips = [Trip("car_a", arrive_at=a.a_arrive, priority=a.a_priority),
             Trip("car_b", arrive_at=a.b_arrive, priority=a.b_priority)]
    res = run_simulation(trips, policy=a.policy, network=net, log=None if a.quiet else (lambda e: print(e)))
    print()
    print(f"SIMULATION (no hardware, no motors)  policy={a.policy}  latency={a.latency * 1000:.0f} ms  loss={a.loss:.0%}")
    print(f"{'vehicle':<8}{'priority':>9}{'arrived':>9}{'entered':>9}{'exited':>9}{'wait':>8}")
    for t in res.trips:
        print(f"{t.vehicle:<8}{t.priority:>9}{t.arrive:>9.2f}{(t.enter or float('nan')):>9.2f}"
              f"{(t.exit or float('nan')):>9.2f}{t.wait(res.duration):>8.2f}")
    print(f"crossing order: {' -> '.join(res.enter_order())}   overlaps: {res.overlaps()}   "
          f"all completed: {res.all_completed}")
    if a.timeline:
        with open(a.timeline, "w", encoding="utf-8") as f:
            f.write(timeline_svg([(f"policy = {a.policy}", res)]))
        print(f"timeline written to {a.timeline}")
    return 0 if res.overlaps() == 0 and res.all_completed else 1


def _experiment(a: argparse.Namespace) -> int:
    prefix = os.path.join(a.out, "results") if a.out else None
    if a.out:
        os.makedirs(a.out, exist_ok=True)
    print(experiment.main(prefix, seed=a.seed, n=a.trials))
    if prefix:
        print(f"written: {prefix}.md and {prefix}.json")
    return 0


def _plot(a: argparse.Namespace) -> int:
    sc = {s.name.split()[0]: s for s in experiment.named_scenarios()}
    panels = []
    for pol, label in (("fcfs", "First-come-first-served"), ("priority", "Priority-aware")):
        s = sc[a.scenario]
        panels.append((f"{label}  ({s.name})", run_simulation(s.trips, policy=pol, network=SimNetwork(seed=1, latency_s=s.latency_s))))
    svg = timeline_svg(panels, t_max=a.t_max)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"timeline written to {a.out}")
    return 0


def _perception(a: argparse.Namespace) -> int:
    paths = sorted(p for pattern in a.images for p in (glob.glob(pattern) or [pattern]))
    det = perception.StopLineDetector()
    rc = 0
    for path in paths:
        try:
            r = det.detect(perception.read_ppm(path))
        except (OSError, ValueError) as exc:
            print(f"{path}: INVALID ({exc})")
            rc = 1
            continue
        print(f"{path}: {r.status:<9} coverage={r.coverage:.3f} "
              f"centroid_y={'-' if r.centroid_y is None else f'{r.centroid_y:.2f}'} "
              f"at_stop_line={r.at_stop_line}  [{r.detail}]")
    return rc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m carcomms", description="CarComms: two-car intersection coordination")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="run one two-car scenario in the simulator and print the decision log")
    s.add_argument("--policy", default="priority", choices=["priority", "fcfs"])
    s.add_argument("--a-priority", type=int, default=0)
    s.add_argument("--b-priority", type=int, default=5)
    s.add_argument("--a-arrive", type=float, default=1.0)
    s.add_argument("--b-arrive", type=float, default=1.0)
    s.add_argument("--latency", type=float, default=0.05, help="one-way message delay in seconds")
    s.add_argument("--loss", type=float, default=0.0, help="fraction of messages lost, 0..1")
    s.add_argument("--duplicate", type=float, default=0.0, help="fraction of messages delivered twice")
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("--timeline", default=None, help="write an SVG timeline to this path")
    s.add_argument("--quiet", action="store_true", help="only the summary, no event log")
    s.set_defaults(fn=_simulate)

    e = sub.add_parser("experiment", help="compare first-come-first-served with the priority policy")
    e.add_argument("--out", default=None, help="directory for results.md / results.json")
    e.add_argument("--seed", type=int, default=1)
    e.add_argument("--trials", type=int, default=2000)
    e.set_defaults(fn=_experiment)

    g = sub.add_parser("plot", help="draw the FCFS vs priority timeline of a named scenario as SVG")
    g.add_argument("--scenario", default="S1b", help="S1a, S1b, S2, S3, S4 or S5")
    g.add_argument("--out", default="docs/timeline.svg")
    g.add_argument("--t-max", type=float, default=6.0)
    g.set_defaults(fn=_plot)

    v = sub.add_parser("vehicle", help="run ONE vehicle as a real-time UDP process (motors off)")
    vehicle.add_arguments(v)
    v.set_defaults(fn=vehicle.run)

    d = sub.add_parser("udp-demo", help="start two vehicle processes on this machine and verify exclusive access")
    d.add_argument("--policy", default="priority", choices=["priority", "fcfs"])
    d.add_argument("--a-priority", type=int, default=0)
    d.add_argument("--b-priority", type=int, default=5)
    d.add_argument("--a-arrive", type=float, default=1.0)
    d.add_argument("--b-arrive", type=float, default=1.0)
    d.add_argument("--b-sensor-fault-until", type=float, default=0.0)
    d.add_argument("--quiet", action="store_true")
    d.set_defaults(fn=lambda a: demo.run(a.a_priority, a.b_priority, a.a_arrive, a.b_arrive, a.policy,
                                         a.b_sensor_fault_until, a.quiet))

    c = sub.add_parser("perception", help="run the stop-line marker detector on recorded .ppm frames")
    c.add_argument("images", nargs="+", help="PPM files or globs, e.g. examples/frames/*.ppm")
    c.set_defaults(fn=_perception)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
