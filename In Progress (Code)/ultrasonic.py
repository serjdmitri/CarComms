import RPi.GPIO as GPIO
import time
from config import TRIG_PIN, ECHO_PIN

TIMEOUT = 0.1  # seconds before we give up waiting for echo


def setup_ultrasonic():
    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)
    GPIO.output(TRIG_PIN, False)
    time.sleep(0.1)


def get_distance():
    # Send 10us pulse
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, False)

    start = time.time()
    stop = time.time()

    # Wait for echo to go high
    timeout_start = time.time()
    while GPIO.input(ECHO_PIN) == 0:
        start = time.time()
        if time.time() - timeout_start > TIMEOUT:
            return 999  # No echo received

    # Wait for echo to go low
    timeout_start = time.time()
    while GPIO.input(ECHO_PIN) == 1:
        stop = time.time()
        if stop - timeout_start > TIMEOUT:
            return 999  # Echo held too long, object too close or error

    elapsed = stop - start
    distance_cm = (elapsed * 34300) / 2
    return round(distance_cm, 1)
