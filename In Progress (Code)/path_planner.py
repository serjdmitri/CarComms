from imu import update_heading, turn_to_angle
from motor_control import turn_left, turn_right, stop
from config import SAFE_DIST_CM


def choose_direction(dist_left, dist_right):
    # Returns ('left', clearance) or ('right', clearance)
    if dist_left >= dist_right:
        return "left", dist_left
    return "right", dist_right


def execute_turn(direction, current_heading):
    # Calculate exact target angle based on direction
    if direction == "left":
        target = (current_heading - 90) % 360
        turn_fn = lambda: turn_left(60)
    else:
        target = (current_heading + 90) % 360
        turn_fn = lambda: turn_right(60)

    turn_to_angle(target, turn_fn)
    stop()
    return target


def is_path_clear(dist_left, dist_right):
    return max(dist_left, dist_right) >= SAFE_DIST_CM
