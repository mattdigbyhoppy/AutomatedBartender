import RPi.GPIO as GPIO
import time
from threading import Thread

GPIO.setmode(GPIO.BCM)

def init_pumps():
    for pin in config.PUMP_PINS.values():
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)

def prime_all():
    """Run each pump for its priming time in sequence."""
    for fluid, pin in config.PUMP_PINS.items():
        duration = config.PRIMING_TIME[fluid]
        GPIO.output(pin, GPIO.LOW)
        time.sleep(duration)
        GPIO.output(pin, GPIO.HIGH)

def dispense(ingredients, update_callback=None):
    """
    ingredients: dict of fluid->milliliters.
    update_callback(percent_complete, poured_ml)
    """
    total = sum(ingredients.values())
    poured = 0

    threads = []
    for fluid, ml in ingredients.items():
        pin = config.PUMP_PINS[fluid]
        t = Thread(target=_run_pump, args=(pin, ml, update_callback, lambda: poured))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

def _run_pump(pin, ml, cb, get_poured):
    """Turn on pump pin for time proportional to ml."""
    rate = config.FLOW_RATE  # ml per second
    duration = ml / rate
    GPIO.output(pin, GPIO.LOW)
    start = time.time()
    while time.time() - start < duration:
        poured = get_poured() + rate * (time.time() - start)
        if cb: cb(poured)
        time.sleep(0.1)
    GPIO.output(pin, GPIO.HIGH)
