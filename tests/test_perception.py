import os
import tempfile
import unittest

from carcomms import perception as p

FRAMES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "frames")


class PerceptionTests(unittest.TestCase):
    def setUp(self):
        self.det = p.StopLineDetector()

    def test_clear_floor_has_no_marker(self):
        r = self.det.detect(p.synthetic_frame(80, 60))
        self.assertEqual((r.status, r.at_stop_line), ("NOT_FOUND", False))

    def test_far_marker_is_seen_but_not_at_the_line(self):
        r = self.det.detect(p.synthetic_frame(80, 60, line_y=(10, 15)))
        self.assertEqual(r.status, "FOUND")
        self.assertFalse(r.at_stop_line)

    def test_near_marker_is_at_the_line(self):
        r = self.det.detect(p.synthetic_frame(80, 60, line_y=(44, 52)))
        self.assertEqual(r.status, "FOUND")
        self.assertTrue(r.at_stop_line)

    def test_invalid_frames_are_reported_not_guessed(self):
        strict = p.StopLineDetector(stride=1)   # with stride > 1 only sampled pixels are validated
        for bad in (None, [], [[]], 42, [[(1, 2, 3)], [(1, 2, 3), (4, 5, 6)]],
                    [[(1, 2, 3), (1, 2, 3)], [(1, 2, 3), (300, 0, 0)]],
                    [[(1, 2, 3), "x"], [(1, 2, 3), (1, 2, 3)]]):
            self.assertEqual(strict.detect(bad).status, "INVALID", msg=repr(bad))

    def test_ppm_round_trip_and_recorded_examples(self):
        frame = p.synthetic_frame(20, 10, line_y=(5, 8))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.ppm")
            p.write_ppm(path, frame)
            self.assertEqual(p.read_ppm(path), frame)
        got = {n: self.det.detect(p.read_ppm(os.path.join(FRAMES, n))) for n in os.listdir(FRAMES) if n.endswith(".ppm")}
        self.assertEqual(got["clear_floor.ppm"].status, "NOT_FOUND")
        self.assertFalse(got["stop_line_far.ppm"].at_stop_line)
        self.assertTrue(got["stop_line_near.ppm"].at_stop_line)

    def test_truncated_ppm_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.ppm")
            with open(path, "wb") as f:
                f.write(b"P6\n10 10\n255\nabc")
            with self.assertRaises(ValueError):
                p.read_ppm(path)


if __name__ == "__main__":
    unittest.main()
