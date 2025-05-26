#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO
from hx711 import HX711
import statistics

# ————— CONFIG ————— #
DT_PIN   = 16    # HX711 DOUT → GPIO16 (BCM)
CLK_PIN  = 4     # HX711 SCK  → GPIO4  (BCM)
SAMPLES  = 20    # how many raw readings per output
# —————————————— #

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Initialize HX711 on channel A, gain=128
hx = HX711(
    dout_pin       = DT_PIN,
    pd_sck_pin     = CLK_PIN,
    gain_channel_A = 128,
    select_channel = 'A'
)
hx.reset()

def read_signed():
    """Read one 24-bit sample and return it as a signed int."""
    raw = hx._read()      # returns a string of the 24-bit unsigned value
    v = int(raw)
    if v & (1 << 23):     # two's-complement negative?
        v -= (1 << 24)
    return v

try:
    print("Live raw ADC (median of 20 samples): Ctrl-C to quit\n")
    while True:
        burst = [read_signed() for _ in range(SAMPLES)]
        med   = statistics.median(burst)
        print(f"{med:.0f}", end="\r", flush=True)
        time.sleep(1.0)

except KeyboardInterrupt:
    pass

finally:
    print("\nCleaning up GPIO…")
    GPIO.cleanup()
