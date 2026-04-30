import RPi.GPIO as GPIO
from config import IN1, IN2, IN3, IN4, ENA, ENB

pwm_a = None
pwm_b = None


def setup_motors():
    global pwm_a, pwm_b
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for pin in [IN1, IN2, IN3, IN4, ENA, ENB]:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, False)
    pwm_a = GPIO.PWM(ENA, 1000)
    pwm_b = GPIO.PWM(ENB, 1000)
    pwm_a.start(0)
    pwm_b.start(0)


def set_speed(left, right):
    # left, right: -100 to 100. Negative = backward.
    GPIO.output(IN1, GPIO.HIGH if left > 0 else GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH if left < 0 else GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH if right > 0 else GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH if right < 0 else GPIO.LOW)
    pwm_a.ChangeDutyCycle(min(abs(left), 100))
    pwm_b.ChangeDutyCycle(min(abs(right), 100))


def stop():
    set_speed(0, 0)


def forward(speed=70):
    set_speed(speed, speed)


def backward(speed=70):
    set_speed(-speed, -speed)


def turn_left(speed=60):
    set_speed(-speed, speed)


def turn_right(speed=60):
    set_speed(speed, -speed)


def cleanup():
    stop()
    if pwm_a:
        pwm_a.stop()
    if pwm_b:
        pwm_b.stop()
    GPIO.cleanup()
