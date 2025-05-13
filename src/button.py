#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO
from functools import partial

# BCM pin numbers (as-wired)
BTN_CONFIRM = 12
BTN_CANCEL  = 6
BTN_MENU    = 5
BTN_SPECIAL = 13

ALL_BUTTONS = (BTN_CONFIRM, BTN_CANCEL, BTN_MENU, BTN_SPECIAL)
NAMES = {
    BTN_CONFIRM: "CONFIRM",
    BTN_CANCEL:  "CANCEL",
    BTN_MENU:    "MENU",
    BTN_SPECIAL: "SPECIAL",
}

def callback(name, channel):
    print(f"[!] {name} pressed on BCM {channel}")

if __name__ == "__main__":
    GPIO.setwarnings(False)
    GPIO.cleanup()             # clear any old detectors
    GPIO.setmode(GPIO.BCM)

    # 1) Setup inputs
    for btn in ALL_BUTTONS:
        GPIO.setup(btn, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    # 2) Attach exactly one interrupt per pin
    for btn in ALL_BUTTONS:
        try:
            GPIO.remove_event_detect(btn)
        except Exception:
            pass

        try:
            GPIO.add_event_detect(
                btn,
                GPIO.RISING,
                callback=partial(callback, NAMES[btn]),
                bouncetime=200
            )
            print(f"[OK]  Interrupt on {NAMES[btn]} (BCM {btn})")
        except RuntimeError as e:
            print(f"[FAIL] {NAMES[btn]} (BCM {btn}): {e}")

    print("** Interrupt tester running. Press a button. CTRL-C to quit. **")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
        print("Exiting.")
