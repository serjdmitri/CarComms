# Smart Navigation Robot — V2V Autonomous System

> **Status: In Progress** — Robot 1 built and functional. Robot 2 ~40% complete.

Two Raspberry Pi 4 robots that navigate autonomously and communicate with each other over WiFi in real time, demonstrating Vehicle-to-Vehicle (V2V) communication. The core idea mirrors what self-driving car research teams are working on: multiple agents sharing sensor data and making coordinated movement decisions without any human input.

---

## How It Works

Each robot runs a continuous control loop that fuses data from four sensors, plans a path, and broadcasts its state to the other robot 20 times per second over UDP.

### Sensor Fusion

| Sensor | Role |
|--------|------|
| HC-SR04 + SG90 Servo | Scans left and right to measure clearance on each side |
| Pi Camera Module 2 | Visual obstacle detection via OpenCV |
| MPU-6050 IMU | Tracks heading angle so turns are precise, not guessed |
| NEO-6M GPS | Broadcasts real-world coordinates over V2V |

### Angle-Based Navigation

Most basic obstacle-avoiding robots turn randomly when they detect something. These robots do not. The ultrasonic sensor sweeps left and right, measures clearance on both sides, and the path planner calculates the optimal turn angle before the robot moves. The IMU then tracks rotation so the robot lands on the correct heading instead of approximating it. This is a meaningful step up from the typical "if obstacle, turn right" logic.

### V2V Communication

Both robots broadcast a state packet over WiFi UDP at 20Hz containing:
- Current GPS coordinates
- Heading angle from the IMU
- Distance to nearest obstacle from the ultrasonic sensor
- Robot ID

When the received packet shows the other robot is within a collision threshold, the lower-priority robot stops and holds position while the other navigates around it. No central coordinator. Each robot makes its own decision based on shared data.

### The Demo

Two robots drive toward each other from opposite ends of a course. Both are broadcasting state. When V2V data indicates a collision course, one stops. The other calculates a path around it using angle-based navigation and continues. They then resume toward their original headings. This is the same coordination concept used in intersection management research for autonomous vehicles.

---

## Hardware

### Per Robot

| Component | Purpose |
|-----------|---------|
| Raspberry Pi 4 Model B (4GB) | Main compute + WiFi |
| Elegoo Robot Car Chassis V4 | Chassis, motors, wheels |
| L298N Motor Driver | Controls DC motors via GPIO PWM |
| HC-SR04 Ultrasonic Sensor | Distance measurement |
| SG90 Servo | Pans ultrasonic sensor left/right |
| Pi Camera Module 2 | Visual input (CSI ribbon) |
| MPU-6050 IMU | Gyroscope-based heading tracking |
| NEO-6M GPS Module | UART-based position data |
| 3-Channel Line Sensor | Ground/surface detection |
| LM2596 Buck Converter | Steps battery voltage to 5V for Pi |
| GeeekPi ICE Tower Fan | Active cooling under sensor load |
| GPIO Expansion Board (ribbon-cable T-type) | Breaks out GPIO without blocking fan |

---

## Software Architecture

```
Smart-Navigation-Robot/
├── config.py          # Pin definitions, robot ID, network settings
├── motor_control.py   # L298N abstraction (forward, reverse, turn, stop)
├── ultrasonic.py      # HC-SR04 sweep + clearance measurement
├── imu.py             # MPU-6050 heading via gyroscope integration
├── gps_module.py      # NEO-6M UART parsing with pynmea2
├── camera.py          # Frame capture + OpenCV obstacle detection
├── v2v_comm.py        # UDP broadcast sender + receiver threads
├── path_planner.py    # Angle calculation + IMU-guided turn execution
└── main.py            # Main control loop + V2V coordination logic
```

All code is Python 3. Each module is independently testable.

---

## Setup

### 1. Flash OS

Use Raspberry Pi Imager. Enable SSH, set hostname to `robot1` or `robot2`, configure WiFi before first boot.

### 2. Enable Interfaces

```bash
sudo raspi-config
```

Enable: Camera, I2C, Serial Port (disable login shell, keep hardware serial), SSH.

### 3. Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-smbus i2c-tools gpsd gpsd-clients
pip3 install RPi.GPIO picamera2 smbus2 pynmea2 pyserial opencv-python
```

### 4. Verify Hardware

```bash
# MPU-6050 should show up at 0x68
sudo i2cdetect -y 1

# Camera check
libcamera-hello --timeout 5000

# GPS — confirm NMEA sentences are coming through
sudo gpsd /dev/ttyS0 -F /var/run/gpsd.sock
cgps -s
```

### 5. Configure

In `config.py`, set:
- `ROBOT_ID` — `"robot1"` or `"robot2"`
- `BROADCAST_IP` — your subnet's broadcast address (e.g., `192.168.1.255`)

### 6. Run

```bash
python3 main.py
```

---

## Build Progress

| Component | Robot 1 | Robot 2 |
|-----------|---------|---------|
| Chassis + motors | Done | Done |
| L298N motor driver | Done | In progress |
| HC-SR04 + servo | Done | Pending |
| MPU-6050 IMU | Done | Pending |
| NEO-6M GPS | Done | Pending |
| Pi Camera | Mounted | Pending |
| Buck converter + power | Done | In progress |
| V2V software layer | In progress | — |
| Angle-based nav | In progress | — |

---

## Why V2V Matters

Vehicle-to-Vehicle communication is an active research area at companies like Waymo and in university autonomous systems labs. The core challenge is the same at any scale: agents need to share state and make decentralized decisions fast enough to avoid collisions. This project is a small, working proof of concept of that architecture — built on commodity hardware with open-source software.

---

## Author

**Sergey Dmitriev**  
NSU University School, Hollywood, Florida  
GitHub: [serjdmitri](https://github.com/serjdmitri)
