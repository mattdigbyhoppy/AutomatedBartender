#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO
from hx711 import HX711
from statistics import StatisticsError

# ————— HARDWARE CONFIG ————— #
DT_PIN         = 16   # HX711 DOUT → GPIO16
CLK_PIN        = 4    # HX711 SCK  → GPIO4
CAL_SAMPLES    = 50   # ≤99 for get_raw_data_mean
READ_SAMPLES   = 20   # samples per live display
ZERO_THRESHOLD = 0.5  # grams below which we'll snap to 0.0
# ———————————————— #

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# Instantiate HX711 on channel A, gain=128
hx = HX711(
    dout_pin       = DT_PIN,
    pd_sck_pin     = CLK_PIN,
    gain_channel_A = 128,
    select_channel = 'A'
)

# Reset and enable built-in outlier filter
hx.reset()
hx.set_data_filter(hx.outliers_filter)

def raw_mean(n):
    """
    Return the average of `n` raw ADC readings, with fallback if the filter fails.
    """
    try:
        val = hx.get_raw_data_mean(readings=n)
        if val is False:
            raise RuntimeError("ADC read failed")
    except (RuntimeError, StatisticsError):
        # fallback: temporarily disable filter
        old_filter = hx._data_filter
        hx._data_filter = lambda data: data
        val = hx.get_raw_data_mean(readings=n)
        hx._data_filter = old_filter
    return val

# --- 1) Tare (zero) --- #
input("❯ Clear plate & press Enter to tare…")
plate_offset = raw_mean(CAL_SAMPLES)
hx.offset    = plate_offset
print(f"✔ Tare offset = {plate_offset:.1f} counts\n")

# --- 2) Calibration with known weight --- #
input("❯ Place a known weight on the plate and press Enter…")
loaded = raw_mean(CAL_SAMPLES)
delta  = loaded - plate_offset
print(f"→ Loaded raw = {loaded:.1f}   Δ = {delta:.1f} counts")

known_g = float(input("❯ Enter known weight in grams: "))
ratio   = delta / known_g
hx.set_scale_ratio(ratio)
print(f"✔ Scale ratio = {ratio:.4f} counts/g\n")

# --- Pause before live measurements --- #
input("❯ Remove the calibration weight and press Enter to start live measurements…")

# --- 3) Live weight readout --- #
print("Reading weight in grams (Ctrl-C to exit):\n")
try:
    while True:
        # get raw average and compute weight
        current = raw_mean(READ_SAMPLES)
        weight  = (current - plate_offset) / ratio
        # apply dead-zone around zero to suppress noise
        if abs(weight) < ZERO_THRESHOLD:
            weight = 0.0
        print(f"{weight:.2f} g")
        time.sleep(1.0)

except KeyboardInterrupt:
    pass

finally:
    GPIO.cleanup()
