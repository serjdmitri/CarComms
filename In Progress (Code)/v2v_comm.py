import socket
import json
import threading
import time
from config import ROBOT_ID, V2V_PORT, BROADCAST_IP, BROADCAST_RATE_HZ

other_robot = {}
_lock = threading.Lock()


def broadcast_state(distance, heading, lat, lon):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        payload = json.dumps({
            "id": ROBOT_ID,
            "distance": distance,
            "heading": heading,
            "lat": lat,
            "lon": lon,
            "timestamp": time.time()
        })
        sock.sendto(payload.encode(), (BROADCAST_IP, V2V_PORT))
        sock.close()
    except Exception as e:
        print(f"V2V broadcast error: {e}")


def _listen():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", V2V_PORT))
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            msg = json.loads(data.decode())
            if msg["id"] != ROBOT_ID:
                with _lock:
                    other_robot.update(msg)
        except Exception:
            pass


def get_other_robot():
    with _lock:
        return dict(other_robot)


def setup_v2v():
    t = threading.Thread(target=_listen, daemon=True)
    t.start()
