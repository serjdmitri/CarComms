"""Transports: a deterministic simulated network and a real UDP socket.

``SimNetwork`` lets tests and experiments inject latency, jitter, loss,
duplication and outage windows reproducibly (seeded RNG, no wall clock).
``UdpTransport`` is the real thing for two processes or two Raspberry Pis.
"""

from __future__ import annotations

import heapq
import random
import socket
from typing import Iterable, List, Optional, Sequence, Tuple


class SimNetwork:
    """Point-to-point datagram network with configurable impairments."""

    def __init__(self, seed: int = 0, latency_s: float = 0.05, jitter_s: float = 0.0,
                 loss: float = 0.0, duplicate: float = 0.0,
                 outages: Sequence[Tuple[float, float]] = ()) -> None:
        self.rng = random.Random(seed)
        self.latency_s = latency_s
        self.jitter_s = jitter_s
        self.loss = loss
        self.duplicate = duplicate
        self.outages = list(outages)      # [(start, end)): every datagram sent inside is lost
        self._heap: List[Tuple[float, int, str, bytes]] = []
        self._n = 0
        self.sent = 0
        self.dropped = 0
        self.delivered = 0

    def _in_outage(self, now: float) -> bool:
        return any(a <= now < b for a, b in self.outages)

    def _push(self, when: float, dst: str, payload: bytes) -> None:
        self._n += 1
        heapq.heappush(self._heap, (when, self._n, dst, payload))

    def send(self, now: float, dst: str, payload: bytes) -> None:
        self.sent += 1
        if self._in_outage(now) or self.rng.random() < self.loss:
            self.dropped += 1
            return
        copies = 2 if self.rng.random() < self.duplicate else 1
        for _ in range(copies):
            jitter = self.rng.uniform(0.0, self.jitter_s) if self.jitter_s else 0.0
            self._push(now + self.latency_s + jitter, dst, payload)

    def inject(self, when: float, dst: str, payload: bytes) -> None:
        """Deliver an arbitrary datagram (garbage, replay, stale copy) at ``when``."""
        self._push(when, dst, payload)

    def deliver(self, now: float) -> List[Tuple[str, bytes]]:
        ready: List[Tuple[str, bytes]] = []
        while self._heap and self._heap[0][0] <= now + 1e-9:
            _, _, dst, payload = heapq.heappop(self._heap)
            self.delivered += 1
            ready.append((dst, payload))
        return ready


class UdpTransport:
    """Non-blocking UDP unicast between two known endpoints."""

    def __init__(self, listen: Tuple[str, int], peer: Tuple[str, int]) -> None:
        self.peer = peer
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(listen)
        self.sock.setblocking(False)

    def send(self, payload: bytes) -> None:
        try:
            self.sock.sendto(payload, self.peer)
        except OSError:
            pass  # unreachable peer/interface down: the protocol treats it as loss

    def poll(self) -> Iterable[bytes]:
        while True:
            try:
                data, _addr = self.sock.recvfrom(2048)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            yield data

    def close(self) -> None:
        self.sock.close()


def parse_endpoint(text: str, default_host: Optional[str] = None) -> Tuple[str, int]:
    """Parse ``host:port`` (or just ``port``) into a tuple."""
    if ":" in text:
        host, port = text.rsplit(":", 1)
    elif default_host is not None:
        host, port = default_host, text
    else:
        raise ValueError(f"expected host:port, got {text!r}")
    return host, int(port)
