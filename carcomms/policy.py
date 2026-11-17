"""Crossing-order policies.

A policy turns a request into a sort key; the request with the *smaller* key
goes first. Both vehicles evaluate the same keys (they are carried in the
state messages), so both reach the same order. Keys are totally ordered:
the final element is the vehicle id, which breaks every remaining tie
deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class RequestView:
    sender: str
    priority: int
    req_ts: int      # Lamport timestamp of the request
    req: int         # request number


class Policy:
    name = "abstract"

    def key(self, r: RequestView) -> Tuple:
        raise NotImplementedError


class PriorityPolicy(Policy):
    """Higher priority first; then earlier (Lamport) request; then vehicle id."""

    name = "priority"

    def key(self, r: RequestView) -> Tuple:
        return (-r.priority, r.req_ts, r.sender)


class FcfsPolicy(Policy):
    """Baseline: ignore priority. Earlier (Lamport) request first; then vehicle id.

    "First come" means first *observed*: requests made within one message
    latency of each other can carry the same Lamport timestamp, and then the
    vehicle id decides.
    """

    name = "fcfs"

    def key(self, r: RequestView) -> Tuple:
        return (r.req_ts, r.sender)


POLICIES: Dict[str, Policy] = {p.name: p for p in (PriorityPolicy(), FcfsPolicy())}


def get_policy(name: str) -> Policy:
    try:
        return POLICIES[name]
    except KeyError:
        raise ValueError(f"unknown policy {name!r}; choose from {sorted(POLICIES)}") from None
