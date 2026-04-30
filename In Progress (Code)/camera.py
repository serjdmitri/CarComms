from picamera2 import Picamera2
import cv2
import numpy as np
import threading

camera = None
latest_frame = None
frame_lock = threading.Lock()


def setup_camera():
    global camera
    camera = Picamera2()
    config = camera.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"})
    camera.configure(config)
    camera.start()

    t = threading.Thread(target=_capture_loop, daemon=True)
    t.start()


def _capture_loop():
    global latest_frame
    while True:
        frame = camera.capture_array()
        with frame_lock:
            latest_frame = frame


def get_frame():
    with frame_lock:
        return latest_frame.copy() if latest_frame is not None else None


def detect_obstacle_camera():
    # Basic obstacle detection using color/contrast change in lower half of frame
    frame = get_frame()
    if frame is None:
        return False
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    lower_half = gray[240:, :]
    edges = cv2.Canny(lower_half, 50, 150)
    edge_density = np.sum(edges > 0) / edges.size
    # If more than 15% of the lower frame is edges, likely an obstacle
    return edge_density > 0.15
