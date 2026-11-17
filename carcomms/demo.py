"""Launch two vehicle processes on this machine and check they never share the intersection."""

from __future__ import annotations

import argparse
import re
import socket
import subprocess
import sys
import threading
import time
from typing import List, Tuple

EVENT = re.compile(r"t=\s*([0-9.]+)\s+(car_\w+)\s+(REQUEST|ENTER|EXIT)\b")
TIMED = re.compile(r"^t=\s*(-?[0-9.]+)")


def _free_ports(n: int) -> List[int]:
    socks = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(n)]
    try:
        for s in socks:
            s.bind(("127.0.0.1", 0))
        return [s.getsockname()[1] for s in socks]
    finally:
        for s in socks:
            s.close()


def run(a_priority: int, b_priority: int, a_arrive: float, b_arrive: float, policy: str,
        sensor_fault_until: float = 0.0, quiet: bool = False) -> int:
    import os
    port_a, port_b = _free_ports(2)
    # time.monotonic() is shared by processes on one machine, so one t0 aligns both logs.
    t0 = time.monotonic() + 0.5
    base = [sys.executable, "-u", "-m", "carcomms", "vehicle", "--policy", policy, "--t0", repr(t0)]
    cmds = {
        "car_a": base + ["--id", "car_a", "--listen", f"127.0.0.1:{port_a}", "--peer", f"127.0.0.1:{port_b}",
                         "--priority", str(a_priority), "--arrive-after", str(a_arrive)],
        "car_b": base + ["--id", "car_b", "--listen", f"127.0.0.1:{port_b}", "--peer", f"127.0.0.1:{port_a}",
                         "--priority", str(b_priority), "--arrive-after", str(b_arrive),
                         "--sensor-fault-until", str(sensor_fault_until)],
    }
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    procs = {k: subprocess.Popen(c, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
             for k, c in cmds.items()}
    lines: List[Tuple[float, str, str]] = []
    lock = threading.Lock()

    def pump(name, proc):
        for line in proc.stdout:
            line = line.rstrip("\n")
            with lock:
                lines.append((time.monotonic(), name, line))

    threads = [threading.Thread(target=pump, args=(k, p), daemon=True) for k, p in procs.items()]
    for th in threads:
        th.start()
    codes = {}
    for k, p in procs.items():
        try:
            codes[k] = p.wait(timeout=90)
        except subprocess.TimeoutExpired:
            p.kill()
            codes[k] = -9
    for th in threads:
        th.join(timeout=2)

    def key(item):
        m = TIMED.match(item[2])
        if m:
            return (float(m.group(1)), item[0])
        return (-1e9 if "start" in item[2] else 1e9, item[0])

    if not quiet:
        for _, _name, line in sorted(lines, key=key):
            print(line)

    enters, exits = {}, {}
    for _, _, line in lines:
        m = EVENT.search(line)
        if not m:
            continue
        t, who, kind = float(m.group(1)), m.group(2), m.group(3)
        if kind == "ENTER":
            enters[who] = t
        elif kind == "EXIT":
            exits[who] = t
    ok = set(enters) == set(exits) == {"car_a", "car_b"} and all(c == 0 for c in codes.values())
    overlap = False
    if ok:
        a0, a1, b0, b1 = enters["car_a"], exits["car_a"], enters["car_b"], exits["car_b"]
        overlap = a0 < b1 and b0 < a1
    first = min(enters, key=enters.get) if enters else "?"
    print()
    print(f"two OS processes, real UDP sockets, policy={policy}")
    print(f"enter times : {enters}")
    print(f"exit times  : {exits}")
    print(f"went first  : {first}")
    print(f"overlap in intersection: {'YES (BUG)' if overlap else 'no'}; exit codes: {codes}")
    return 0 if ok and not overlap else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--policy", default="priority", choices=["priority", "fcfs"])
    p.add_argument("--a-priority", type=int, default=0)
    p.add_argument("--b-priority", type=int, default=5)
    p.add_argument("--a-arrive", type=float, default=1.0)
    p.add_argument("--b-arrive", type=float, default=1.0)
    p.add_argument("--b-sensor-fault-until", type=float, default=0.0,
                   help="make car_b's simulated distance sensor invalid until this time (shows the hold)")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)
    return run(a.a_priority, a.b_priority, a.a_arrive, a.b_arrive, a.policy, a.b_sensor_fault_until, a.quiet)


if __name__ == "__main__":
    sys.exit(main())
