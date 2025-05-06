import RPi.GPIO as GPIO
from hx711 import HX711
import time

GPIO.setmode(GPIO.BCM)

# Infrared break‑beam sensor for glass detection
GPIO.setup(config.IR_SENSOR_PIN, GPIO.IN)

# Weight sensor (HX711) for backup glass detect & live volume
hx = HX711(config.HX711_DT, config.HX711_SCK)

def is_glass_present():
    """Return True if either IR beam is broken or weight > threshold."""
    ir = not GPIO.input(config.IR_SENSOR_PIN)  # beam broken = 0
    weight = hx.get_weight_mean(5)             # average of 5 readings
    return ir or (weight > 50)  # e.g., >50 grams

def get_weight():
    """Return current weight in grams."""
    return hx.get_weight_mean(5)
