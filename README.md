# Smart Navigation Robot — V2V Autonomous System

> **Status: In Progress** — Robot 1 operational as an obstacle-avoiding robot. Robot 2 partially assembled, wiring in progress.

Two Raspberry Pi 4 robots designed to navigate autonomously and communicate with each other over WiFi in real time, demonstrating a small-scale version of Vehicle-to-Vehicle (V2V) communication. The long-term goal is a working demo where two robots detect each other, coordinate who stops and who moves, and navigate around each other without any human input.

---

## Why I Built This

I was watching the news one evening and saw a report about two soccer players who were killed in a car accident at an intersection. It stuck with me. Later, scrolling through social media on an anniversary of the release of Fast and Furious, I came across posts about Paul Walker and how he died in a car crash. Two separate moments, same thought: these deaths were preventable.

I started looking at what Tesla and other companies were doing with autonomous vehicles and the idea clicked. If every car on the road could sense its surroundings and communicate its position and speed to the cars around it in real time, intersection collisions like those would not happen. The car would know another vehicle was coming before any human could react.

That led me further. If roads were fully autonomous, you would not need lanes as wide or as many of them, because the cars would coordinate tightly and safely. Narrower roads mean less pavement, less land use, less heat absorption, less runoff. It connects directly to reducing urban sprawl and lowering carbon emissions. The safety problem and the environmental problem have the same solution.

This project is my attempt to build a small, working version of that idea. I am a high school student learning as I go, so this is not a finished system. But the concept it is based on is real, the hardware is real, and the problem it points at is real.

---

## What It Does

### Current State
Robot 1 is fully assembled and working as a standalone obstacle-avoiding robot. It detects objects in front of it, scans left and right with the ultrasonic sensor on a servo, and turns toward whichever side has more clearance. Robot 2 is partially built with the main components assembled but wiring not yet complete.

### The Goal
The full system has two robots communicating over WiFi using UDP broadcast packets sent 20 times per second. Each packet contains the robot's ID, GPS coordinates, heading angle, and distance to the nearest obstacle. When one robot's data shows the other is close and on a converging path, the lower-priority robot stops while the other navigates around it. No central server, no remote control. Each robot decides on its own based on what it receives.

### The Key Navigation Idea
Most basic obstacle-avoiding robots just turn a fixed amount when they hit something. These robots are designed to scan both sides first, calculate which direction gives the most clearance, and use the IMU to rotate to that specific angle rather than guessing. The goal is navigation that is deliberate rather than random.

---

## Hardware

### Per Robot

| Component | Purpose |
|-----------|---------|
| Raspberry Pi 4 Model B (4GB) | Main compute, runs all Python code, handles WiFi |
| Elegoo Robot Car Chassis V4 | Chassis, DC motors, wheels |
| L298N Motor Driver | Controls left and right motors via GPIO PWM signals |
| HC-SR04 Ultrasonic Sensor | Measures distance to obstacles |
| SG90 Servo | Pans the ultrasonic sensor left and right to scan |
| Pi Camera Module 2 | Visual input via CSI ribbon cable |
| MPU-6050 IMU | Gyroscope and accelerometer for heading tracking |
| NEO-6M GPS Module | UART-based real-world position data |
| 3-Channel Line Sensor | Ground surface detection |
| LM2596 Buck Converter | Steps battery voltage down to stable 5V for the Pi |
| GeeekPi ICE Tower Fan | Active cooling under continuous sensor load |
| GPIO Expansion Board (ribbon-cable T-type) | Breaks out GPIO pins without physically blocking the fan |

The ribbon-cable T-type expansion board is a deliberate choice. A stacking GPIO board would conflict with the ICE Tower fan. The ribbon cable solves that without losing any GPIO access.

---

## Tech Stack

All code runs on **Python 3** on each Raspberry Pi 4. No external servers or cloud services. Everything runs locally on the robots.

### Libraries

| Library | Purpose |
|---------|---------|
| `RPi.GPIO` | Controls GPIO pins for motors, ultrasonic sensor, and servo |
| `smbus2` | I2C communication with the MPU-6050 IMU |
| `pyserial` | UART communication with the NEO-6M GPS module |
| `pynmea2` | Parses NMEA sentences from the GPS into usable coordinates |
| `picamera2` | Captures frames from the Pi Camera Module 2 |
| `opencv-python` | Processes camera frames for visual obstacle detection |
| `socket` | Built-in Python library used for UDP broadcast communication between robots |

### Communication Protocol
The two robots talk to each other using **UDP broadcast sockets** over the local WiFi network. UDP is used instead of TCP because the priority is speed, not guaranteed delivery. A slightly outdated position packet is better than a delayed one. Each robot sends 20 packets per second and listens for incoming packets on a background thread so communication never blocks the main navigation loop.

---

## Planned Software Architecture

The codebase will be split into focused modules so each component can be tested independently before being integrated.

| File | Responsibility |
|------|---------------|
| `config.py` | Pin definitions, robot ID, network settings, tunable constants |
| `motor_control.py` | L298N abstraction: forward, reverse, turn, stop, speed control |
| `ultrasonic.py` | HC-SR04 distance reading, servo sweep, clearance measurement |
| `imu.py` | MPU-6050 heading tracking via gyroscope integration |
| `gps_module.py` | NEO-6M UART parsing, coordinate output |
| `camera.py` | Frame capture, OpenCV-based obstacle detection |
| `v2v_comm.py` | UDP broadcast sender and listener threads |
| `path_planner.py` | Clearance-based angle calculation, IMU-guided turn execution |
| `main.py` | Main control loop, sensor fusion, V2V coordination logic |

Wiring diagrams and setup instructions will be added as the build progresses.

---

## Build Progress

| Component | Robot 1 | Robot 2 |
|-----------|---------|---------|
| Chassis and motors | Done | Done |
| L298N motor driver | Done | In progress |
| HC-SR04 + servo mount | Done | Pending |
| MPU-6050 IMU | Done | Pending |
| NEO-6M GPS | Done | Pending |
| Pi Camera Module 2 | Mounted | Pending |
| Buck converter and power | Done | In progress |
| GPIO expansion board | Done | Pending |
| V2V communication layer | Not started | — |
| Angle-based navigation | Not started | — |

---

## The Bigger Picture

If roads were fully autonomous, the benefits go beyond just preventing crashes. Vehicles that communicate and coordinate in real time do not need the same buffer space between lanes. Roads could be narrower. Less land cleared for pavement means less heat island effect, less stormwater runoff, and more space left as natural habitat. The safety argument and the environmental argument point at the same solution.

This project is one small step toward understanding how that kind of system works at a fundamental level.

---

## Author

**Sergey Dmitriev**  
NSU University School, Hollywood, Florida  
GitHub: [serjdmitri](https://github.com/serjdmitri)
