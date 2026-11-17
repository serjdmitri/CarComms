"""Smoke tests for the pieces that touch sockets, processes and the CLI."""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout

from carcomms import cli, experiment
from carcomms.network import SimNetwork, UdpTransport, parse_endpoint

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class RuntimeTests(unittest.TestCase):
    def test_hardware_module_imports_without_a_raspberry_pi(self):
        import importlib
        mod = importlib.import_module("carcomms.hardware")
        if "RPi" not in sys.modules:
            with self.assertRaises(RuntimeError):
                mod.hcsr04_reader()

    def test_sim_network_is_deterministic(self):
        def run():
            n = SimNetwork(seed=5, latency_s=0.05, jitter_s=0.1, loss=0.3, duplicate=0.3)
            for i in range(50):
                n.send(i * 0.05, "x", bytes([i]))
            return [(round(t, 3), d) for t in [i * 0.05 for i in range(100)] for _, d in n.deliver(t)]
        self.assertEqual(run(), run())

    def test_udp_transport_loopback(self):
        a = UdpTransport(("127.0.0.1", 0), ("127.0.0.1", 9))
        b = UdpTransport(("127.0.0.1", 0), ("127.0.0.1", a.sock.getsockname()[1]))
        try:
            b.send(b"hello")
            for _ in range(100):
                got = list(a.poll())
                if got:
                    break
                import time
                time.sleep(0.01)
            self.assertEqual(got, [b"hello"])
            self.assertEqual(list(a.poll()), [])        # non-blocking: nothing left
        finally:
            a.close()
            b.close()

    def test_parse_endpoint(self):
        self.assertEqual(parse_endpoint("10.0.0.2:5005"), ("10.0.0.2", 5005))
        self.assertEqual(parse_endpoint("5005", "127.0.0.1"), ("127.0.0.1", 5005))
        with self.assertRaises(ValueError):
            parse_endpoint("5005")

    def test_cli_simulate_exit_code_and_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["simulate", "--quiet"])
        self.assertEqual(rc, 0)
        self.assertIn("crossing order: car_b -> car_a", buf.getvalue())

    def test_experiment_is_reproducible_and_safe(self):
        a = experiment.run_all(seed=1, n=40)
        b = experiment.run_all(seed=1, n=40)
        self.assertEqual(a, b)
        self.assertEqual(a["random_arrivals"]["overlaps"], 0)
        self.assertEqual(a["random_arrivals"]["unfinished"], 0)
        self.assertEqual(a["random_arrivals_10pct_loss"]["unfinished"], 0)

    def test_two_real_processes_share_the_intersection_exclusively(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["udp-demo", "--quiet"])
        self.assertEqual(rc, 0, buf.getvalue())
        self.assertIn("overlap in intersection: no", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
