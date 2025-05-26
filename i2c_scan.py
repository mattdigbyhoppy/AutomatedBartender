#!/usr/bin/env python3
import smbus

bus = smbus.SMBus(1)   # Use I²C bus #1

found = []
for addr in range(0x03, 0x78):
    try:
        bus.read_byte(addr)
        found.append(addr)
    except OSError:
        pass

if found:
    print("I²C device(s) at:", [hex(a) for a in found])
else:
    print("No I²C devices found")
