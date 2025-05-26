#!/usr/bin/env python3
from luma.core.interface.serial import i2c
from luma.oled.device        import ssd1306
from luma.core.render        import canvas
from PIL                     import ImageFont

# 1) Initialize I²C. On the Pi, bus=1, address=0x3C:
serial = i2c(port=1, address=0x3D)

# 2) Create an SSD1306 device instance at 128×64:
device = ssd1306(serial, rotate=0)

# 3) Load the default 8×8 font:
font = ImageFont.load_default()

# 4) Draw into the display buffer:
with canvas(device) as draw:
    # outline a rectangle around the edge
    draw.rectangle(device.bounding_box, fill="black")


