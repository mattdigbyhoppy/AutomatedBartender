#!/usr/bin/env python3
from gpiozero import DigitalInputDevice
from time    import sleep

# Use BCM pin 17 (physical pin 11)
sensor = DigitalInputDevice(22, pull_up=True)

print("Starting break-beam test. Cover/uncover the beam:")
try:
    while True:
        if sensor.is_active:
            # beam intact (pulled high)
            print("Beam BROKEN")
        else:
            # beam broken (pulled low)
            print("Beam OK")
        sleep(0.5)
except KeyboardInterrupt:
    print("\nExiting")
