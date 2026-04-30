import serial
import pynmea2
import threading
from config import GPS_PORT, GPS_BAUD

lat = 0.0
lon = 0.0
gps_lock = threading.Lock()


def _read_gps():
    global lat, lon
    try:
        with serial.Serial(GPS_PORT, GPS_BAUD, timeout=1) as ser:
            while True:
                line = ser.readline().decode("ascii", errors="replace").strip()
                if line.startswith("$GPGGA") or line.startswith("$GPRMC"):
                    try:
                        msg = pynmea2.parse(line)
                        with gps_lock:
                            lat = msg.latitude
                            lon = msg.longitude
                    except pynmea2.ParseError:
                        pass
    except serial.SerialException as e:
        print(f"GPS error: {e}")


def setup_gps():
    # Run GPS reading in background so it never blocks the main loop
    t = threading.Thread(target=_read_gps, daemon=True)
    t.start()


def get_position():
    with gps_lock:
        return lat, lon
