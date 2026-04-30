# Build Log — Smart Navigation Robot

## Robot 1

### April 2026 — Initial Build (Robotics Camp)
- Assembled Elegoo chassis with DC motors and wheels
- Mounted L298N motor driver
- Installed Raspberry Pi 4 on plastic nylon standoffs
- Wired HC-SR04 ultrasonic sensor on SG90 servo mount
- Installed LM2596 buck converter for power regulation
- Mounted 3-channel Elegoo line sensor on underside
- Connected basic Dupont wiring
- Achieved basic obstacle avoidance behavior

### April 2026 — Upgrade Phase (Current)
- [ ] Install GeeekPi ICE Tower fan on Pi 4
- [ ] Install GPIO expansion board
- [ ] Wire MPU-6050 IMU (I2C — pins 2, 3)
- [ ] Wire NEO-6M GPS module (UART — pins 8, 10)
- [ ] Install Pi Camera Module 2 via CSI ribbon cable
- [ ] Test all sensors individually before running main.py
- [ ] Run full main.py and test obstacle avoidance with angle-based navigation

---

## Robot 2

### May 2026 — Full Build
- [ ] Assemble Elegoo V4 chassis
- [ ] Mount Pi 4 on nylon standoffs
- [ ] Install ICE Tower fan
- [ ] Wire L298N motor driver
- [ ] Wire LM2596 buck converter
- [ ] Wire HC-SR04 ultrasonic on SG90 servo
- [ ] Install 3-channel line sensor
- [ ] Wire MPU-6050 IMU
- [ ] Wire NEO-6M GPS module
- [ ] Install Pi Camera Module 2
- [ ] Install GPIO expansion board
- [ ] Flash SD card with Raspberry Pi OS
- [ ] Set hostname to robot2 in raspi-config
- [ ] Update ROBOT_ID to "robot2" in config.py
- [ ] Test all sensors individually
- [ ] Run full main.py independently

---

## V2V Testing

### Target: June 2026
- [ ] Connect both robots to same WiFi network
- [ ] Confirm UDP broadcast packets received on both sides
- [ ] Demo 1: Two robots drive toward each other, detect via V2V, one stops
- [ ] Demo 2: One robot navigates around the other
- [ ] Record demo video for GitHub
- [ ] Update README with demo video link

---

## Known Issues
- HC-SR04 Echo pin outputs 5V — voltage divider required before connecting to Pi GPIO
- GPS requires outdoor clear sky view for satellite fix
- First GPS cold start takes 1-2 minutes

## Parts Reference
| Part | ASIN | Robot |
|------|------|-------|
| GeeekPi ICE Tower Fan | B0B9KM9WYL | Both |
| MPU-6050 IMU | B01DK83ZYQ | Both |
| NEO-6M GPS | B01D1D0F5M | Both |
| GPIO Expansion Board | B07MCW4KCM | Both |
| Elegoo V4 Kit | B07KPZ8RSZ | Robot 2 |
| Pi 4 4GB | B07TC2BK1X | Robot 2 |
| Pi Camera Module 2 | B01ER2SKFS | Robot 2 |
| L298N Motor Driver | B0CR6BX5QL | Robot 2 |
| LM2596 Buck Converter | B07MKQXNWG | Robot 2 |
| Nylon Standoffs | B0FPMC9917 | Robot 2 |
