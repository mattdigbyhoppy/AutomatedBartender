import RPi.GPIO as GPIO
import time

# GPIO pins for relays controlling pumps
pump_pins = [24, 25, 12]

# Setup GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Setup pins as output
for pin in pump_pins:
    GPIO.setup(pin, GPIO.OUT)

# Function to turn all pumps off
def all_pumps_off():
    for pin in pump_pins:
        GPIO.output(pin, GPIO.LOW)

try:
    while True:
        # Turn all pumps off for 5 seconds
        all_pumps_off()
        print("All pumps off")
        time.sleep(5)

        # Cycle through each pump one at a time
        for pin in pump_pins:
            GPIO.output(pin, GPIO.HIGH)
            print(f"Pump on: {pin}")
            time.sleep(1)  # Adjust timing as needed
            GPIO.output(pin, GPIO.LOW)

except KeyboardInterrupt:
    print("\nExiting program")

finally:
    # Cleanup GPIO pins
    GPIO.cleanup()
