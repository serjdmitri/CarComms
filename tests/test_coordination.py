"""Behaviour of the two-vehicle coordination protocol.

Most tests go through ``run_simulation`` (deterministic, seeded). A few drive two
``Coordinator`` objects by hand to pin down exact message interleavings.
"""

import unittest

from carcomms.coordinator import Action, Coordinator, CoordinatorConfig
from carcomms.messages import PHASE_CROSSING, PHASE_IDLE, StateMessage, decode
from carcomms.network import SimNetwork
from carcomms.policy import FcfsPolicy, PriorityPolicy
from carcomms.sensors import classify_raw
from carcomms.simulation import Trip, run_simulation

OK = classify_raw(100.0, 0.0)


def ok_reading(now):
    return classify_raw(100.0, now)


def two(policy="priority", **kw):
    """Two hand-driven coordinators plus a helper that delivers one state message."""
    mk = PriorityPolicy if policy == "priority" else FcfsPolicy
    a = Coordinator("car_a", mk(), peer_id="car_b", boot_id=1, **kw)
    b = Coordinator("car_b", mk(), peer_id="car_a", boot_id=2, **kw)
    return a, b


def deliver(src_msgs, dst, now):
    for m in src_msgs:
        dst.on_datagram(now, m.encode())


class PriorityAndTieBreaking(unittest.TestCase):
    def run_pair(self, policy, a_prio, b_prio, a_at=1.0, b_at=1.0, **kw):
        return run_simulation([Trip("car_a", arrive_at=a_at, priority=a_prio),
                               Trip("car_b", arrive_at=b_at, priority=b_prio)], policy=policy, **kw)

    def test_higher_priority_goes_first_when_simultaneous(self):
        r = self.run_pair("priority", a_prio=0, b_prio=5)
        self.assertEqual(r.enter_order(), ["car_b", "car_a"])
        r = self.run_pair("priority", a_prio=5, b_prio=0)
        self.assertEqual(r.enter_order(), ["car_a", "car_b"])

    def test_equal_priority_simultaneous_is_deterministic(self):
        orders = {tuple(self.run_pair("priority", 3, 3).enter_order()) for _ in range(5)}
        self.assertEqual(orders, {("car_a", "car_b")})   # vehicle id breaks the tie

    def test_fcfs_ignores_priority(self):
        r = self.run_pair("fcfs", a_prio=0, b_prio=9)
        self.assertEqual(r.enter_order(), ["car_a", "car_b"])  # same Lamport ts -> id decides

    def test_both_vehicles_choose_the_same_order(self):
        """Exactly one grant is given in a contested start; the loser is the one that grants."""
        for policy in ("priority", "fcfs"):
            for a_prio, b_prio in ((0, 5), (5, 0), (2, 2)):
                r = self.run_pair(policy, a_prio, b_prio)
                grants = [e for e in r.events if e.kind == "GRANT_GIVEN"]
                first_winner = r.enter_order()[0]
                first_grant = grants[0]
                self.assertNotEqual(first_grant.vehicle, first_winner,
                                    msg=f"{policy} {a_prio}/{b_prio}: the winner must not be the first granter")
                self.assertEqual(first_grant.detail.split()[1], first_winner)

    def test_earlier_request_wins_when_priorities_equal(self):
        # car_b asks 0.5 s before car_a has even arrived
        r = self.run_pair("priority", 0, 0, a_at=2.0, b_at=1.0)
        self.assertEqual(r.enter_order(), ["car_b", "car_a"])

    def test_priority_arriving_after_other_has_entered_cannot_preempt(self):
        r = self.run_pair("priority", a_prio=0, b_prio=9, a_at=1.0, b_at=1.5)
        self.assertEqual(r.enter_order(), ["car_a", "car_b"])
        self.assertEqual(r.overlaps(), 0)


class ExclusiveAccess(unittest.TestCase):
    def test_no_overlap_in_basic_scenarios(self):
        for policy in ("priority", "fcfs"):
            for a_at, b_at in ((1.0, 1.0), (1.0, 1.02), (1.0, 1.04), (1.0, 1.06), (1.0, 1.5), (1.0, 3.0)):
                r = run_simulation([Trip("car_a", arrive_at=a_at), Trip("car_b", arrive_at=b_at, priority=7)],
                                   policy=policy)
                self.assertEqual(r.overlaps(), 0, msg=f"{policy} {a_at}/{b_at}")
                self.assertEqual(r.conflict_ticks, 0)
                self.assertTrue(r.all_completed)

    def test_idle_grant_then_higher_priority_request_still_waits(self):
        """car_b grants while idle, then raises a *higher*-priority request of its own.
        The grant travels in the same state message as the request, so car_a is committed."""
        a, b = two()
        a.request_crossing(1.00, priority=0)
        deliver(a.tick(1.00, OK).messages, b, 1.01)          # b (idle) grants a
        self.assertEqual(b.grant, 1)
        b.request_crossing(1.02, priority=9)                  # b now wants the box with top priority
        out_b = b.tick(1.02, OK)
        self.assertEqual(out_b.action, Action.WAIT)           # b must wait: it granted a
        deliver(out_b.messages, a, 1.03)
        self.assertEqual(a.grant, 0, "a must NOT yield: b's message already carries the grant for a")
        out_a = a.tick(1.04, ok_reading(1.04))
        self.assertEqual(out_a.action, Action.PROCEED)
        # b stays out until a releases, however long it waits
        for t in (1.5, 2.0, 3.0):
            deliver(a.tick(t, ok_reading(t)).messages, b, t)
            self.assertEqual(b.tick(t, ok_reading(t)).action, Action.WAIT)
        a.exit_intersection(3.1)
        deliver(a.tick(3.1, ok_reading(3.1)).messages, b, 3.15)
        deliver(b.tick(3.15, ok_reading(3.15)).messages, a, 3.2)
        self.assertEqual(b.tick(3.2, ok_reading(3.2)).action, Action.PROCEED)

    def test_release_then_subsequent_access_alternates(self):
        r = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_a", gap_after_previous=0.2),
                            Trip("car_b", arrive_at=1.0), Trip("car_b", gap_after_previous=0.2)])
        self.assertTrue(r.all_completed)
        self.assertEqual(len(r.trips), 4)
        self.assertEqual(r.overlaps(), 0)
        self.assertEqual(r.enter_order(), ["car_a", "car_b", "car_a", "car_b"])

    def test_repeat_priority_requests_cannot_jump_a_waiting_car(self):
        """An exiting car grants the already-waiting peer before it can re-request."""
        trips = [Trip("car_b", arrive_at=0.5, priority=9), Trip("car_b", gap_after_previous=0.0, priority=9),
                 Trip("car_b", gap_after_previous=0.0, priority=9), Trip("car_a", arrive_at=1.0, priority=0)]
        r = run_simulation(trips, policy="priority")
        self.assertEqual(r.overlaps(), 0)
        self.assertEqual(r.enter_order(), ["car_b", "car_a", "car_b", "car_b"])

    def test_events_log_the_full_lifecycle(self):
        r = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_b", arrive_at=4.0)])
        kinds = [e.kind for e in r.events if e.vehicle == "car_a"]
        for needed in ("REQUEST", "ENTER", "EXIT", "RELEASE"):
            self.assertIn(needed, kinds)
        self.assertEqual(kinds.index("REQUEST") < kinds.index("ENTER") < kinds.index("EXIT"), True)
        # car_b (idle) granted car_a's request
        self.assertEqual([e.kind for e in r.events if e.vehicle == "car_b" and e.kind == "GRANT_GIVEN"][:1],
                         ["GRANT_GIVEN"])


def peer_msg(seq, **over):
    base = dict(sender="car_b", seq=seq, policy="priority", phase="REQUESTING", req=1, priority=9,
                movement="straight", clock=1, req_ts=1, grant=0, released=0, sent_at=0.0, boot=2)
    base.update(over)
    return StateMessage(**base)


class DefenceInDepth(unittest.TestCase):
    """States the honest protocol never produces; a buggy or hostile peer might."""

    def test_never_enters_while_holding_an_outstanding_grant_of_its_own(self):
        a, _ = two()
        a.request_crossing(0.0, priority=0)
        a.on_message(0.01, peer_msg(1))                         # b outranks a: a yields (grant -> 1)
        self.assertEqual(a.grant, 1)
        a.on_message(0.02, peer_msg(2, grant=1))                # b now *also* claims to grant a
        self.assertEqual(a.tick(0.03, ok_reading(0.03)).action, Action.WAIT)
        self.assertEqual(a.phase, "REQUESTING")

    def test_a_crossing_vehicle_never_grants(self):
        a, _ = two()
        a.request_crossing(0.0, priority=0)
        a.on_message(0.01, peer_msg(1, phase="IDLE", req=0, priority=0, req_ts=0, grant=1, clock=0))
        a.tick(0.05, ok_reading(0.05))
        self.assertEqual(a.phase, PHASE_CROSSING)
        # a higher-priority request arrives whose message forgets the grant: still must not grant
        a.on_message(0.1, peer_msg(3, grant=0))
        self.assertEqual(a.grant, 0)
        self.assertEqual(a.phase, PHASE_CROSSING)

    def test_peer_claiming_to_cross_without_our_grant_latches_a_fault(self):
        a, _ = two()
        a.on_message(0.0, peer_msg(1, phase="CROSSING", req=1, released=0))
        self.assertIn("without our grant", a.fault)
        a.request_crossing(0.1)
        self.assertEqual(a.tick(0.2, ok_reading(0.2)).action, Action.WAIT)


class MessageHandling(unittest.TestCase):
    def test_duplicates_are_dropped_and_do_not_change_behaviour(self):
        base = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_b", arrive_at=1.0, priority=5)])
        dup = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_b", arrive_at=1.0, priority=5)],
                             network=SimNetwork(seed=3, latency_s=0.05, duplicate=1.0))
        self.assertEqual(dup.enter_order(), base.enter_order())
        self.assertEqual(dup.overlaps(), 0)
        self.assertGreater(sum(c.get("dropped_duplicate", 0) for c in dup.counters.values()), 0)

    def test_stale_and_reordered_messages_are_dropped(self):
        a, b = two()
        a.request_crossing(0.0)
        m1 = a.tick(0.0, OK).messages[0]
        m2 = a.tick(0.05, OK).messages[0]
        self.assertTrue(b.on_message(0.1, m2))
        self.assertFalse(b.on_message(0.11, m1))              # older seq arrives late
        self.assertFalse(b.on_message(0.12, m2))              # exact duplicate
        self.assertEqual(b.counters["dropped_stale"], 1)
        self.assertEqual(b.counters["dropped_duplicate"], 1)
        self.assertEqual(b.peer.seq, m2.seq)

    def test_late_old_copy_cannot_revoke_progress(self):
        """A delayed copy of the peer's *request* arriving after its release is ignored."""
        a, b = two()
        a.request_crossing(0.0)
        req_msg = a.tick(0.0, OK).messages[0]
        deliver([req_msg], b, 0.05)
        deliver(b.tick(0.05, OK).messages, a, 0.1)
        a.tick(0.1, OK)
        self.assertEqual(a.phase, PHASE_CROSSING)
        a.exit_intersection(1.0)
        rel = a.tick(1.0, OK).messages[0]
        deliver([rel], b, 1.05)
        self.assertEqual(b.grant, 0)
        self.assertFalse(b.on_message(1.1, req_msg))          # delayed duplicate of the old request
        self.assertEqual(b.grant, 0, "must not re-grant a finished request")

    def test_garbage_datagrams_are_counted_and_ignored(self):
        a, b = two()
        for junk in (b"", b"\x00\x01", b"{}", b'{"sender":"car_a"}'):
            self.assertFalse(b.on_datagram(0.0, junk))
        self.assertEqual(b.counters["dropped_invalid"], 4)
        self.assertIsNone(b.peer)

    def test_own_broadcast_echo_and_unknown_sender_are_ignored(self):
        a, b = two()
        own = b.tick(0.0, OK).messages[0]
        self.assertFalse(b.on_message(0.0, own))
        self.assertEqual(b.counters["ignored_self_echo"], 1)
        c = Coordinator("car_c", PriorityPolicy(), boot_id=3)
        c.request_crossing(0.0)
        self.assertFalse(b.on_message(0.1, c.tick(0.0, OK).messages[0]))
        self.assertEqual(b.counters["dropped_unknown_sender"], 1)

    def test_policy_mismatch_latches_fault_and_blocks_entry(self):
        a = Coordinator("car_a", PriorityPolicy(), peer_id="car_b", boot_id=1)
        b = Coordinator("car_b", FcfsPolicy(), peer_id="car_a", boot_id=2)
        a.request_crossing(0.0)
        deliver(a.tick(0.0, OK).messages, b, 0.01)
        self.assertIn("policy mismatch", b.fault)
        self.assertEqual(b.grant, 0)                           # a faulted coordinator grants nothing

    def test_peer_reboot_holds_until_operator_clears(self):
        a, b = two()
        a.request_crossing(0.0)
        deliver(a.tick(0.0, OK).messages, b, 0.01)             # b grants a
        self.assertEqual(b.grant, 1)
        # a reboots: new boot id, sequence numbers start again at 1
        a2 = Coordinator("car_a", PriorityPolicy(), peer_id="car_b", boot_id=99)
        deliver(a2.tick(0.5, OK).messages, b, 0.51)
        self.assertEqual(b.counters["peer_restarts"], 1)
        self.assertIn("restarted", b.fault)
        b.request_crossing(0.6)
        self.assertEqual(b.tick(0.6, OK).action, Action.WAIT)
        self.assertEqual(b.grant, 1, "grant to the old incarnation is kept while faulted")
        b.clear_fault(1.0)
        self.assertEqual(b.grant, 0)
        deliver(a2.tick(1.0, OK).messages, b, 1.0)             # a2 is idle -> grants b
        deliver(b.tick(1.0, OK).messages, a2, 1.01)
        deliver(a2.tick(1.05, OK).messages, b, 1.06)
        self.assertEqual(b.tick(1.1, ok_reading(1.1)).action, Action.PROCEED)


class CommunicationLoss(unittest.TestCase):
    def test_silent_peer_never_means_empty_intersection(self):
        c = Coordinator("car_a", PriorityPolicy(), peer_id="car_b", boot_id=1)
        c.request_crossing(0.0)
        for step in range(0, 400):                              # 20 s of silence
            out = c.tick(step * 0.05, ok_reading(step * 0.05))
            self.assertEqual(out.action, Action.WAIT)
        self.assertEqual(c.phase, "REQUESTING")
        self.assertIn("peer silent", out.reason)

    def test_outage_during_a_crossing_does_not_let_the_other_car_in(self):
        """car_a crosses 1.0-2.6; the link dies at 1.5 and returns at 6.0; car_b arrives at 2.0.
        When the crossing time has elapsed, car_b must still wait for a real release."""
        net = SimNetwork(latency_s=0.05, outages=[(1.5, 6.0)])
        r = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_b", arrive_at=2.0, priority=9)],
                           network=net)
        a, b = (t for t in sorted(r.trips, key=lambda t: t.vehicle))
        self.assertTrue(r.all_completed)
        self.assertGreaterEqual(b.enter, 6.0, "car_b entered during the outage")
        self.assertGreaterEqual(b.enter, a.exit)
        self.assertEqual(r.overlaps(), 0)
        self.assertTrue(any(e.kind == "LINK_DOWN" for e in r.events))
        self.assertTrue(any(e.kind == "LINK_UP" for e in r.events))

    def test_outage_before_any_request_delays_but_does_not_break(self):
        net = SimNetwork(latency_s=0.05, outages=[(0.0, 3.0)])
        r = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_b", arrive_at=1.0)], network=net)
        self.assertTrue(r.all_completed)
        self.assertEqual(r.overlaps(), 0)
        self.assertGreaterEqual(min(t.enter for t in r.trips), 3.0)

    def test_link_loss_while_holding_a_grant_blocks_entry(self):
        a, b = two()
        a.request_crossing(0.0)
        deliver(a.tick(0.0, OK).messages, b, 0.01)
        deliver(b.tick(0.01, OK).messages, a, 0.02)             # a now holds b's grant
        out = a.tick(2.0, ok_reading(2.0))                      # ...but nothing was heard for 2 s
        self.assertEqual(out.action, Action.WAIT)
        self.assertIn("link down", out.reason)
        deliver(b.tick(2.1, OK).messages, a, 2.1)               # link returns
        self.assertEqual(a.tick(2.1, ok_reading(2.1)).action, Action.PROCEED)

    def test_vehicle_already_crossing_can_still_exit_when_link_is_down(self):
        a, b = two()
        a.request_crossing(0.0)
        deliver(a.tick(0.0, OK).messages, b, 0.01)
        deliver(b.tick(0.01, OK).messages, a, 0.02)
        a.tick(0.05, ok_reading(0.05))
        self.assertEqual(a.phase, PHASE_CROSSING)
        a.tick(5.0, ok_reading(5.0))                            # link long dead
        self.assertEqual(a.phase, PHASE_CROSSING)               # never abandons the crossing
        self.assertTrue(a.exit_intersection(5.0))
        self.assertEqual(a.phase, PHASE_IDLE)


class SensorGating(unittest.TestCase):
    def test_invalid_sensor_blocks_entry_until_it_recovers(self):
        for bad in (float("nan"), None, 999, -3, 5000):
            r = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_b", arrive_at=10.0)],
                               sensors={"car_a": lambda t, bad=bad: bad if t < 3.0 else 100.0})
            a = [t for t in r.trips if t.vehicle == "car_a"][0]
            self.assertGreaterEqual(a.enter, 3.0, msg=f"entered on bad reading {bad!r}")
            self.assertTrue(r.all_completed)

    def test_obstacle_ahead_blocks_entry(self):
        r = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_b", arrive_at=10.0)],
                           sensors={"car_a": lambda t: 12.0 if t < 2.5 else 80.0})
        a = [t for t in r.trips if t.vehicle == "car_a"][0]
        self.assertGreaterEqual(a.enter, 2.5)
        self.assertTrue(any(e.kind == "HOLD" and "obstacle" in e.detail for e in r.events))

    def test_blocked_vehicle_blocks_the_peer_too(self):
        r = run_simulation([Trip("car_a", arrive_at=1.0, priority=9), Trip("car_b", arrive_at=1.0)],
                           sensors={"car_a": lambda t: 12.0 if t < 4.0 else 80.0})
        b = [t for t in r.trips if t.vehicle == "car_b"][0]
        self.assertGreaterEqual(b.enter, 4.0 + 1.5)             # waits for a's whole crossing
        self.assertEqual(r.overlaps(), 0)

    def test_sensor_optional_when_not_required(self):
        cfg = CoordinatorConfig(broadcast_interval_s=0.05, require_sensor=False)
        r = run_simulation([Trip("car_a", arrive_at=1.0), Trip("car_b", arrive_at=5.0)], config=cfg,
                           sensors={"car_a": lambda t: None})
        self.assertTrue(r.all_completed)


class SafetySweep(unittest.TestCase):
    def test_random_impairments_never_overlap_and_always_finish(self):
        """200 seeded runs with loss, duplication, jitter and an outage window."""
        import random
        for seed in range(200):
            rng = random.Random(seed)
            net = SimNetwork(seed=seed, latency_s=rng.choice([0.02, 0.05, 0.1]),
                             jitter_s=rng.choice([0.0, 0.05, 0.15]),
                             loss=rng.choice([0.0, 0.2, 0.4]),
                             duplicate=rng.choice([0.0, 0.3]),
                             outages=[(rng.uniform(0, 4), rng.uniform(4, 6))] if seed % 3 == 0 else [])
            trips = [Trip("car_a", arrive_at=rng.uniform(0, 3), priority=rng.choice([0, 0, 5])),
                     Trip("car_a", gap_after_previous=rng.uniform(0, 1)),
                     Trip("car_b", arrive_at=rng.uniform(0, 3), priority=rng.choice([0, 5, 9])),
                     Trip("car_b", gap_after_previous=rng.uniform(0, 1))]
            for policy in ("priority", "fcfs"):
                r = run_simulation(trips, policy=policy, network=net if policy == "priority"
                                   else SimNetwork(seed=seed, latency_s=net.latency_s, jitter_s=net.jitter_s,
                                                   loss=net.loss, duplicate=net.duplicate, outages=net.outages),
                                   max_time=120.0)
                self.assertEqual(r.overlaps(), 0, msg=f"seed {seed} {policy}")
                self.assertEqual(r.conflict_ticks, 0, msg=f"seed {seed} {policy}")
                self.assertTrue(r.all_completed, msg=f"seed {seed} {policy} did not finish")


if __name__ == "__main__":
    unittest.main()
