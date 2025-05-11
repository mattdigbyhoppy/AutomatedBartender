#!/usr/bin/env python3
import time

from luma.core.interface.serial import i2c
from luma.oled.device        import ssd1306
from luma.core.render        import canvas
from PIL                     import ImageFont

# — CONFIGURATION —————————————————————————————————————————
I2C_BUS = 1         # Pi’s I2C bus (pin 3/5)
I2C_ADDR = 0x3D     # address from i2cdetect
ROTATE   = 0        # flip if upside-down
FONT     = ImageFont.load_default()
# —————————————————————————————————————————————————————————

# Initialize the OLED
serial = i2c(port=I2C_BUS, address=I2C_ADDR)
device = ssd1306(serial, rotate=ROTATE)
device.contrast(255)

def get_cpu_temp():
    """Read the Pi’s CPU temp in °C"""
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return float(f.read()) / 1000.0

# Main loop
while True:
    temp = get_cpu_temp()
    text = f"Temp: {temp:.2f} °C"

    with canvas(device) as draw:
        draw.text((0, 0), text, font=FONT, fill="white")

    time.sleep(2)
