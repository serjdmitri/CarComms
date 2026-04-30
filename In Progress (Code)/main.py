import RPi.GPIO as GPIO
import time

from config import OBSTACLE_DIST_CM, V2V_ALERT_DIST_CM, BASE_SPEED, BROADCAST_RATE_HZ
from motor_control import setup_motors, forward, stop, turn_left, turn_right, cleanup
from ultrasonic import setup_ultrasonic, get_distance
from imu import setup_imu, update_heading
from gps_module import setup_gps, get_position
from camera import setup_camera, detect_obstacle_camera
from v2v_comm import setup_v2v, broadcast_state, get_other_robot
from path_planner import choose_direction, execute_turn, is_path_clear

BROADCAST_INTERVAL = 1.0 / BROADCAST_RATE_HZ
last_broadcast = 0


def scan_surroundings():
    # Sweep servo left and right to get distances on each side
    # Servo control added here when servo code is wired
    turn_left(50)
    time.sleep(0.3)
    dist_left = get_distance()

    turn_right(50)
    time.sleep(0.6)
    dist_right = get_distance()

    stop()
    time.sleep(0.1)
    return dist_left, dist_right


def main():
    global last_broadcast

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    setup_motors()
    setup_ultrasonic()
    setup_imu()
    setup_gps()
    setup_camera()
    setup_v2v()

    print("Smart Navigation Robot started.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            now = time.time()
            heading = update_heading()
            dist = get_distance()
            lat, lon = get_position()

            # Broadcast state to other robot at 20Hz
            if now - last_broadcast >= BROADCAST_INTERVAL:
                broadcast_state(dist, heading, lat, lon)
                last_broadcast = now

            # V2V check: if other robot is too close, stop and wait
            other = get_other_robot()
            if other and other.get("distance", 999) < V2V_ALERT_DIST_CM:
                print(f"V2V Alert: {other['id']} is nearby. Stopping.")
                stop()
                time.sleep(0.5)
                continue

            # Camera-based obstacle check as secondary sensor
            camera_sees_obstacle = detect_obstacle_camera()

            if dist < OBSTACLE_DIST_CM or camera_sees_obstacle:
                stop()
                dist_left, dist_right = scan_surroundings()

                if is_path_clear(dist_left, dist_right):
                    direction, clearance = choose_direction(dist_left, dist_right)
                    print(f"Obstacle detected. Turning {direction} ({clearance:.1f}cm clear).")
                    execute_turn(direction, heading)
                else:
                    # Both sides blocked, back up and try again
                    print("Both sides blocked. Backing up.")
                    from motor_control import backward
                    backward(50)
                    time.sleep(0.5)
                    stop()
            else:
                forward(BASE_SPEED)

            time.sleep(0.05)  # 20Hz main loop

    except KeyboardInterrupt:
        print("Stopping robot.")
    finally:
        stop()
        cleanup()


if __name__ == "__main__":
    main()
