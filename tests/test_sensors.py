import unittest

from carcomms.sensors import (DistanceReading, SensorStatus, classify_raw, path_clear,
                              read_safely)

CLEAR = dict(clear_cm=30.0, max_age_s=0.5)


class SensorTests(unittest.TestCase):
    def test_valid_reading(self):
        r = classify_raw(120.0, now=1.0)
        self.assertEqual((r.status, r.distance_cm), (SensorStatus.OK, 120.0))

    def test_invalid_readings(self):
        for raw in (None, float("nan"), float("inf"), -5, 0, 1.0, 401, "12", True, [1]):
            self.assertEqual(classify_raw(raw, 0.0).status, SensorStatus.INVALID, msg=repr(raw))

    def test_legacy_no_echo_is_not_silently_clear(self):
        r = classify_raw(999, 0.0)
        self.assertEqual(r.status, SensorStatus.NO_ECHO)
        ok, why = path_clear(r, 0.0, **CLEAR)
        self.assertFalse(ok)
        self.assertIn("no echo", why)
        ok, _ = path_clear(r, 0.0, no_echo_is_clear=True, **CLEAR)
        self.assertTrue(ok)

    def test_path_clear_thresholds(self):
        self.assertTrue(path_clear(classify_raw(60, 0.0), 0.0, **CLEAR)[0])
        self.assertFalse(path_clear(classify_raw(10, 0.0), 0.0, **CLEAR)[0])

    def test_missing_or_stale_reading_is_not_clear(self):
        self.assertFalse(path_clear(None, 0.0, **CLEAR)[0])
        old = classify_raw(100, now=0.0)
        self.assertFalse(path_clear(old, now=2.0, **CLEAR)[0])

    def test_invalid_reading_is_not_clear(self):
        self.assertFalse(path_clear(DistanceReading(SensorStatus.INVALID, None, 0.0), 0.0, **CLEAR)[0])

    def test_read_error_becomes_invalid(self):
        def boom():
            raise RuntimeError("i2c fell off")
        self.assertEqual(read_safely(boom, 0.0).status, SensorStatus.INVALID)
        self.assertEqual(read_safely(lambda: 50.0, 0.0).status, SensorStatus.OK)


if __name__ == "__main__":
    unittest.main()
