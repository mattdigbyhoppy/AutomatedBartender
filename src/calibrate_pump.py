#!/usr/bin/env python3
import sys
import time
import json
import RPi.GPIO as GPIO

CONFIG_FILE = "pump_config.json"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 calibrate_pump.py <pump_id>")
        print("  where <pump_id> is one of:", ", ".join(load_config().keys()))
        sys.exit(1)

    pump_id = sys.argv[1]
    config = load_config()

    if pump_id not in config:
        print("Error: '%s' not found in %s" % (pump_id, CONFIG_FILE))
        sys.exit(2)

    pin = config[pump_id]["pin"]
    name = config[pump_id]["name"]

    print("Calibrating %s (%s), which is wired to BCM GPIO %d." % (name, pump_id, pin))
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)

    input("Press Enter to run %s for 60 seconds..." % name)

    print("-> %s ON (GPIO %d LOW) for 60 seconds" % (name, pin))
    GPIO.output(pin, GPIO.LOW)
    time.sleep(60)

    print("<- Time's up! Turning %s OFF" % name)
    GPIO.output(pin, GPIO.HIGH)

    GPIO.cleanup()
    print("Done. Exiting.")

if __name__ == "__main__":
    main()
