import smbus2
import time
from config import IMU_ADDRESS

bus = smbus2.SMBus(1)

heading = 0.0
last_time = time.time()


def setup_imu():
    # Wake up the MPU-6050 (it starts in sleep mode)
    bus.write_byte_data(IMU_ADDRESS, 0x6B, 0)
    time.sleep(0.1)


def read_gyro_z():
    high = bus.read_byte_data(IMU_ADDRESS, 0x47)
    low = bus.read_byte_data(IMU_ADDRESS, 0x48)
    raw = (high << 8) | low
    if raw > 32767:
        raw -= 65536
    return raw / 131.0  # Convert to degrees per second


def update_heading():
    global heading, last_time
    now = time.time()
    dt = now - last_time
    last_time = now
    heading = (heading + read_gyro_z() * dt) % 360
    return heading


def turn_to_angle(target_angle, turn_fn, tolerance=3):
    # Rotate using turn_fn until heading matches target within tolerance degrees
    while True:
        current = update_heading()
        diff = (target_angle - current + 360) % 360
        if diff > 180:
            diff -= 360
        if abs(diff) <= tolerance:
            break
        turn_fn()
        time.sleep(0.01)
