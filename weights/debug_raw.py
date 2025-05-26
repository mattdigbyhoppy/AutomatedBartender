import time
import RPi.GPIO as GPIO
from hx711 import HX711

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

DATA_PIN  = 4    # HX711 DOUT → BCM4 (pin 7)
CLOCK_PIN = 16   # HX711 SCK  → BCM16 (pin 36)

hx = HX711(dout_pin=DATA_PIN, pd_sck_pin=CLOCK_PIN)

hx.zero()

while True:
	reading = hx.get_data_mean()
	print(reading)
