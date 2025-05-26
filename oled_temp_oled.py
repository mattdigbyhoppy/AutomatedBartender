#!/usr/bin/env python3
import time

from luma.core.interface.serial import i2c
from luma.oled.device        import ssd1306
from luma.core.render        import canvas
from PIL                     import ImageFont

# ——— CONFIG —————————————————————————————————————————————————————————————
I2C_ADDR = 0x3D    # from your i2cdetect
BUS      = 1       # always 1 on Pi’s 40-pin header
ROTATE   = 0       # or 2 if your module is upside-down
FONT     = ImageFont.load_default()
# ———————————————————————————————————————————————————————————————————————

# Init display
serial = i2c(port=BUS, address=I2C_ADDR)
device = ssd1306(serial, rotate=ROTATE)
device.contrast(255)

def get_cpu_temp():
    # Reads the Pi’s CPU temperature in °C
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return float(f.read()) / 1000.0

while True:
    temp = get_cpu_temp()
    text = f"CPU Temp: {temp:.2f}°C"
    with canvas(device) as draw:
        draw.text((0, 0), text, font=FONT, fill="white")
    time.sleep(2)
