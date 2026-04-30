# ─── Motor Driver (L298N) ───────────────────────────────────────────────────
IN1 = 17
IN2 = 27
IN3 = 22
IN4 = 23
ENA = 18  # Left motor PWM
ENB = 24  # Right motor PWM

# ─── Ultrasonic (HC-SR04) ───────────────────────────────────────────────────
TRIG_PIN = 4
ECHO_PIN = 25  # Use voltage divider! HC-SR04 Echo outputs 5V, Pi GPIO is 3.3V max

# ─── Servo (SG90) ───────────────────────────────────────────────────────────
SERVO_PIN = 12  # Hardware PWM pin

# ─── Line Sensors (Elegoo 3-channel) ────────────────────────────────────────
SENSOR_L = 5
SENSOR_M = 6
SENSOR_R = 13

# ─── IMU (MPU-6050) — uses I2C, automatic pins 2 (SDA) and 3 (SCL) ─────────
IMU_ADDRESS = 0x68

# ─── GPS (NEO-6M) — uses UART (/dev/ttyS0) ──────────────────────────────────
GPS_PORT = "/dev/ttyS0"
GPS_BAUD = 9600

# ─── Camera — uses CSI ribbon port, not GPIO ────────────────────────────────

# ─── V2V Communication ──────────────────────────────────────────────────────
ROBOT_ID = "robot1"           # Change to "robot2" on second robot
V2V_PORT = 5005
BROADCAST_IP = "192.168.1.255"  # Update to match your subnet
BROADCAST_RATE_HZ = 20          # How often to send V2V packets per second

# ─── Navigation ─────────────────────────────────────────────────────────────
OBSTACLE_DIST_CM = 20           # Stop and scan if object closer than this
SAFE_DIST_CM = 30               # Minimum clearance to choose a direction
V2V_ALERT_DIST_CM = 30          # Stop if other robot reports this distance or less
BASE_SPEED = 70                 # Default motor speed (0-100)
TURN_SPEED = 60                 # Speed during turns
