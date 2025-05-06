#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO
from hx711 import HX711

# ——— GPIO SETUP ———
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

DT_PIN  = 16   # HX711 DOUT → GPIO16
CLK_PIN = 4    # HX711 SCK  → GPIO4

# ——— HX711 INITIALIZATION ———
hx = HX711(DT_PIN, CLK_PIN)
hx.reset()      # clear any residual state on the chip

def read_raw():
    # get_raw_data(5) returns a list of strings, one per sample
    raw = hx.get_raw_data(5)
    # convert to ints
    vals = [int(x) for x in raw]
    avg  = sum(vals) / len(vals)
    print(f"Raw: {vals}  →  Avg: {avg:.1f}")

try:
    print("Reading raw HX711 values. Ctrl-C to stop.")
    while True:
        read_raw()
        time.sleep(1.0)

except KeyboardInterrupt:
    print("\nStopped by user.")

finally:
    GPIO.cleanup()
