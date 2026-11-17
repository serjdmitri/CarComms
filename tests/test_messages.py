import json
import unittest

from carcomms.messages import MessageError, StateMessage, decode


def good(**over):
    base = dict(sender="car_a", seq=1, policy="priority", phase="IDLE", req=0, priority=0,
                movement="straight", clock=0, req_ts=0, grant=0, released=0, sent_at=1.5, boot=7)
    base.update(over)
    return StateMessage(**base)


def raw(**over):
    d = json.loads(good().encode())
    d.update(over)
    return json.dumps(d).encode()


class MessageTests(unittest.TestCase):
    def test_round_trip(self):
        m = good(phase="REQUESTING", req=3, released=2, priority=5, grant=2)
        self.assertEqual(decode(m.encode()), m)

    def test_rejects_non_json_and_wrong_shapes(self):
        for payload in (b"", b"not json", b"[]", b"42", b"\xff\xfe", b'{"sender": "x"}'):
            with self.assertRaises(MessageError, msg=repr(payload)):
                decode(payload)

    def test_rejects_wrong_types(self):
        for field, value in (("seq", "1"), ("seq", True), ("seq", -1), ("seq", 1.5),
                             ("priority", 10), ("priority", -1), ("phase", "FLYING"),
                             ("movement", "u-turn"), ("sender", ""), ("sender", 5),
                             ("policy", None), ("version", 99)):
            with self.assertRaises(MessageError, msg=f"{field}={value!r}"):
                decode(raw(**{field: value}))

    def test_rejects_non_finite_timestamp(self):
        with self.assertRaises(MessageError):
            decode(b'{"sent_at": NaN}')
        payload = json.loads(good().encode())
        payload["sent_at"] = float("inf")
        with self.assertRaises(MessageError):
            decode(json.dumps(payload).encode())

    def test_rejects_inconsistent_request_bookkeeping(self):
        with self.assertRaises(MessageError):
            decode(raw(phase="IDLE", req=2, released=1))
        with self.assertRaises(MessageError):
            decode(raw(phase="REQUESTING", req=1, released=1))
        with self.assertRaises(MessageError):
            decode(raw(phase="REQUESTING", req=1, released=2))

    def test_rejects_oversized_datagram(self):
        with self.assertRaises(MessageError):
            decode(b"{" + b" " * 2000 + b"}")


if __name__ == "__main__":
    unittest.main()
