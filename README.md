# Smart Navigation Robot — V2V Autonomous System

Two Raspberry Pi 4 robots that navigate autonomously and communicate with each other wirelessly in real time, demonstrating Vehicle-to-Vehicle (V2V) communication — the same concept used in self-driving car research.

---

## What This Project Does

Each robot uses sensor fusion across four inputs:
- **HC-SR04 Ultrasonic** — detects obstacles and measures distance
- **Pi Camera Module 2** — visual obstacle detection via OpenCV
- **MPU-6050 IMU** — tracks heading angle for precise turning
- **NEO-6M GPS** — real-world coordinates for position broadcasting

The two robots communicate over WiFi using UDP broadcast sockets at 20Hz, sharing their position, heading, and distance data in real time. When one robot detects the other is nearby via V2V data, it stops or reroutes — no human input required.

### The Key Upgrade: Angle-Based Navigation
Most basic obstacle-avoiding robots just randomly turn when they hit something. This robot scans left and right with the ultrasonic sensor, calculates which side has more clearance, then uses the IMU to rotate to the mathematically optimal angle before continuing. This is a fundamental improvement in navigation logic.

### The V2V Demo
Two robots drive toward each other. Both are broadcasting their state over WiFi. When the V2V data shows they are on a collision course, one stops and waits while the other navigates around it. This mirrors how autonomous vehicles coordinate at intersections in real-world research.

---

## Hardware

### Each Robot
| Component | Purpose |
|-----------|---------|
| Raspberry Pi 4 Model B (4GB) | Brain — runs all Python code and WiFi |
| Elegoo Robot Car Chassis V4 | Body, motors, wheels |
| L298N Motor Driver | Controls DC motors from GPIO signals |
| HC-SR04 Ultrasonic Sensor | Distance measurement |
| SG90 Servo | Pans ultrasonic left/right to scan |
| Pi Camera Module 2 | Visual obstacle detection |
| MPU-6050 IMU | Heading angle tracking via gyroscope |
| NEO-6M GPS Module | Real-world position coordinates |
| Elegoo 3-Channel Line Sensor | Ground detection |
| LM2596 Buck Converter | Steps battery voltage down to 5V for Pi |
| GeeekPi ICE Tower Fan | Active cooling under load |
| GPIO 1-to-2 Expansion Board | Doubles available GPIO connections |

---

## Wiring

### Motor Driver (L298N)
| GPIO | Pi Pin | L298N |
|------|--------|-------|
| GPIO 17 | Pin 11 | IN1 |
| GPIO 27 | Pin 13 | IN2 |
| GPIO 22 | Pin 15 | IN3 |
| GPIO 23 | Pin 16 | IN4 |
| GPIO 18 | Pin 12 | ENA (PWM) |
| GPIO 24 | Pin 18 | ENB (PWM) |

### HC-SR04 Ultrasonic
| GPIO | Pi Pin | HC-SR04 |
|------|--------|---------|
| 5V | Pin 4 | VCC |
| GPIO 4 | Pin 7 | TRIG |
| GPIO 25 | Pin 22 | ECHO (use voltage divider!) |
| GND | Pin 9 | GND |

> **WARNING:** HC-SR04 Echo outputs 5V. Pi GPIO max is 3.3V. Use a voltage divider (1kΩ + 2kΩ resistors) or you will damage the Pi.

### MPU-6050 IMU (I2C)
| GPIO | Pi Pin | MPU-6050 |
|------|--------|----------|
| 3.3V | Pin 1 | VCC |
| GND | Pin 14 | GND |
| GPIO 2 (SDA) | Pin 3 | SDA |
| GPIO 3 (SCL) | Pin 5 | SCL |

### NEO-6M GPS (UART)
| GPIO | Pi Pin | GPS |
|------|--------|-----|
| 3.3V | Pin 17 | VCC |
| GND | Pin 20 | GND |
| GPIO 14 (TX) | Pin 8 | RX |
| GPIO 15 (RX) | Pin 10 | TX |

### Pi Camera Module 2
Connects via CSI ribbon cable. Not GPIO.

---

## Software Setup

### 1. Flash Raspberry Pi OS
Use Raspberry Pi Imager. Enable SSH, set hostname to `robot1` (or `robot2`), configure WiFi.

### 2. Enable Interfaces
```bash
sudo raspi-config
```
Enable: Camera, I2C, Serial Port (disable login shell, enable hardware serial), SSH.

### 3. Install Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-smbus i2c-tools gpsd gpsd-clients
pip3 install RPi.GPIO picamera2 smbus2 pynmea2 pyserial opencv-python
```

### 4. Test Components
```bash
# Test I2C (should see 0x68 for MPU-6050)
sudo i2cdetect -y 1

# Test camera
libcamera-hello --timeout 5000

# Test GPS
sudo gpsd /dev/ttyS0 -F /var/run/gpsd.sock
cgps -s
```

### 5. Configure
Edit `config.py`:
- Set `ROBOT_ID` to `"robot1"` or `"robot2"`
- Set `BROADCAST_IP` to your network's broadcast address

### 6. Run
```bash
python3 main.py
```

---

## File Structure

```
Smart-Navigation-Robot/
├── In Progress (Code)/
│   ├── config.py          # Pin definitions and settings
│   ├── motor_control.py   # Motor driver functions
│   ├── ultrasonic.py      # HC-SR04 distance sensing
│   ├── imu.py             # MPU-6050 heading tracking
│   ├── gps_module.py      # NEO-6M GPS reading
│   ├── camera.py          # Camera capture and obstacle detection
│   ├── v2v_comm.py        # WiFi V2V communication
│   ├── path_planner.py    # Angle-based navigation logic
│   └── main.py            # Main control loop
├── In Progress (Build)/
│   └── build_log.md       # Hardware build progress tracker
└── README.md
```

---

## Why This Matters

Every day people die in preventable car crashes. Vehicle-to-Vehicle communication is an active area of research at companies like Waymo, Tesla, and in university robotics labs. The architecture in this project — multiple agents sharing sensor data and making coordinated decisions — is the same fundamental concept that makes real autonomous vehicle systems safe. This robot is a small, working proof of concept of that idea.

---

## Author
Sergey Dmitriev  
NSU University School, Hollywood, Florida  
GitHub: [serjdmitri](https://github.com/serjdmitri)
