import gaugette.ssd1306       # Driver for SSD1306 OLED display
import gaugette.platform     # Underlying platform interface
import gaugette.gpio         # GPIO interface for gaugette
import gaugette.spi          # SPI interface for gaugette
import time                  # Time utilities (sleep)
import sys                   # System utilities
import RPi.GPIO as GPIO      # Raspberry Pi GPIO library
import json                  # JSON parsing for config
import threading             # Threading for pump control
import traceback             # Tracebacks for error handling
import board
import busio
from hx711 import HX711       # HX711 ADC driver for load cell
<<<<<<< HEAD
=======
from adafruit_dotstar import DotStar
from dotstar import Adafruit_DotStar  # NeoPixel-style LED library
>>>>>>> 6c9ec5a (Remove DotStar code & add emergency-stop support)
from menu import MenuItem, Menu, Back, MenuContext, MenuDelegate
from drinks import drink_list, drink_options

# Use BCM (Broadcom) pin numbering
GPIO.setmode(GPIO.BCM)

# Display constants for the OLED
SCREEN_WIDTH    = 128       # OLED width in pixels
SCREEN_HEIGHT   = 64        # OLED height in pixels
OLED_RESET_PIN  = 15        # Reset pin for OLED (not used in luma)
OLED_DC_PIN     = 16        # Data/Command pin for OLED

# Pump flow rate: seconds needed to pour 1 mL
FLOW_RATE = 60.0 / 100.0     # 0.6 s per mL

# Sensor & button GPIO assignments (BCM)
IR_PIN       = 17  # IR break-beam sensor output
TORSION_DT   = 4   # HX711 data pin
TORSION_SCK  = 16  # HX711 clock pin
BTN_CONFIRM  = 5   # Confirm button
BTN_CANCEL   = 6   # Cancel button
BTN_MENU     = 12  # Menu navigation button
BTN_SPECIAL  = 13  # Special function button

# Glass weight thresholds and capacities
SMALL_EMPTY_WT = 66    # Empty small glass weight in grams
LARGE_EMPTY_WT = 371   # Empty large glass weight in grams
SMALL_CAPACITY = 35    # Small glass capacity in mL
LARGE_CAPACITY = 310   # Large glass capacity in mL

# Pump priming duration (to fill lines)
PRIME_TIME     = 10    # Seconds to run all pumps

class Bartender(MenuDelegate):
    def __init__(self):
        """
        Initialize all hardware: buttons, sensors, display, pumps
        """
        self.running = False  # Flag to disable input during pours
        self.emergency_stop = False

        # --- Buttons ---
        for btn in (BTN_CONFIRM, BTN_CANCEL, BTN_MENU, BTN_SPECIAL):
            GPIO.setup(btn, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.btn_confirm = BTN_CONFIRM

        # Emergency-stop listens to Cancel
        GPIO.add_event_detect(BTN_CANCEL,
                              GPIO.FALLING,
                              callback=self.emergency_stop_cb,
                              bouncetime=200)

        # --- Initialize the HX711 load-cell interface ---
        GPIO.setup(TORSION_DT, GPIO.IN)
        GPIO.setup(TORSION_SCK, GPIO.OUT)
        self.hx = HX711(TORSION_DT, TORSION_SCK)
        self.hx.set_reading_format("MSB", "MSB")
        self.hx.set_reference_unit(1)
        self.hx.reset()
        self.hx.tare()

        # --- Initialize IR beam sensor ---
        GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # --- Initialize the OLED via SPI ---
        spi_bus    = 0
        spi_device = 0
        gpio_iface = gaugette.gpio.GPIO()
        spi_iface  = gaugette.spi.SPI(spi_bus, spi_device)
        self.led   = gaugette.ssd1306.SSD1306(
            gpio_iface,
            spi_iface,
            reset_pin=OLED_RESET_PIN,
            dc_pin=OLED_DC_PIN,
            rows=SCREEN_HEIGHT,
            cols=SCREEN_WIDTH
        )
        self.led.begin()
        self.led.clear_display()
        self.led.invert_display()
        time.sleep(0.5)
        self.led.normal_display()
        time.sleep(0.5)

        # --- Load pump config and set up relay outputs ---
        self.pump_configuration = Bartender.readPumpConfiguration()
        for pump in self.pump_configuration:
            pin = self.pump_configuration[pump]["pin"]
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)

        print("Done initializing")

    @staticmethod
    def readPumpConfiguration():
        """
        Read pump_config.json mapping pump names to relay pins and default values.
        """
        return json.load(open('pump_config.json'))

    @staticmethod
    def writePumpConfiguration(configuration):
        """
        Write updated pump configuration back to JSON.
        """
        with open('pump_config.json', 'w') as f:
            json.dump(configuration, f)

    def startInterrupts(self):
        """
        Enable button interrupt(s) for menu navigation.
        """
        GPIO.add_event_detect(
            self.btn_confirm,
            GPIO.FALLING,
            callback=self.confirm_btn,
            bouncetime=200
        )

    def stopInterrupts(self):
        """
        Disable interrupts to prevent input during pours.
        """
        GPIO.remove_event_detect(self.btn_confirm)

    def buildMenu(self, drink_list, drink_options):
        """
        Build the hierarchical menu structure:
        - Top level: drinks + 'Configure'
        - Configure: submenus for each pump to select liquid
        """
        m = Menu("Main Menu")
        for d in drink_list:
            m.addOption(MenuItem('drink', d['name'], {'ingredients': d['ingredients']}))
        config = Menu('Configure')
        for p in sorted(self.pump_configuration.keys()):
            sub = Menu(self.pump_configuration[p]['name'])
            for opt in drink_options:
                selected = '*' if opt['value'] == self.pump_configuration[p]['value'] else ''
                sub.addOption(MenuItem(
                    'pump_selection',
                    opt['name'] + selected,
                    {'key': p, 'value': opt['value']}
                ))
            sub.addOption(Back('Back'))
            sub.setParent(config)
            config.addOption(sub)
        config.addOption(MenuItem('clean', 'Clean'))
        m.addOption(config)
        self.menuContext = MenuContext(m, self)

    def filterDrinks(self, menu):
        """
        Hide drinks from menu if required ingredients aren't configured.
        """
        for item in menu.options:
            if item.type == 'drink':
                ingrs = item.attributes['ingredients']
                item.visible = all(
                    any(ing == self.pump_configuration[p]['value']
                        for p in self.pump_configuration)
                    for ing in ingrs
                )
            elif item.type == 'menu':
                self.filterDrinks(item)

    def selectConfigurations(self, menu):
        """
        Mark the selected fluid for each pump with an asterisk.
        """
        for item in menu.options:
            if item.type == 'pump_selection':
                key = item.attributes['key']
                if self.pump_configuration[key]['value'] == item.attributes['value']:
                    item.name = item.name.rstrip('*') + ' *'
            elif item.type == 'menu':
                self.selectConfigurations(item)

    def prepareForRender(self, menu):
        self.filterDrinks(menu)
        self.selectConfigurations(menu)
        return True

    def menuItemClicked(self, menuItem):
        if menuItem.type == 'drink':
            self.makeDrink(menuItem.name, menuItem.attributes['ingredients'])
            return True
        if menuItem.type == 'pump_selection':
            key = menuItem.attributes['key']
            self.pump_configuration[key]['value'] = menuItem.attributes['value']
            Bartender.writePumpConfiguration(self.pump_configuration)
            return True
        if menuItem.type == 'clean':
            self.clean()
            return True
        return False

    def clean(self):
        """
        Run all pumps for a fixed time (clean cycle).
        """
        self.running = True
        wait = 20
        threads = []
        for p in self.pump_configuration:
            pin = self.pump_configuration[p]['pin']
            threads.append(threading.Thread(target=self.pour, args=(pin, wait)))
        for t in threads: t.start()
        self.progressBar(wait)
        for t in threads: t.join()
        self.menuContext.showMenu()
        time.sleep(2)
        self.running = False

    def displayMenuItem(self, menuItem):
        self.led.clear_display()
        self.led.draw_text2(0, 20, menuItem.name, 2)
        self.led.display()

    def pour(self, pin, wait):
        """
        Activate pump, but break early on emergency_stop.
        """
        GPIO.output(pin, GPIO.LOW)
        elapsed = 0.0
        step    = 0.1
        while elapsed < wait and not self.emergency_stop:
            time.sleep(step)
            elapsed += step
        GPIO.output(pin, GPIO.HIGH)

    def progressBar(self, waitTime):
        """
        Draw progress, but exit loop on emergency_stop.
        """
        interval = waitTime / 100.0
        for pct in range(101):
            if self.emergency_stop:
                break
            self.led.clear_display()
            self.updateProgressBar(pct)
            self.led.display()
            time.sleep(interval)

    def emergency_stop_cb(self, channel):
        """
        Cancel button pressed → abort everything & return to main menu.
        """
        self.emergency_stop = True
        self.running = False
        self.led.clear_display()
        self.led.draw_text2(0, 20, "!! EMERGENCY !!", 2)
        self.led.display()
        time.sleep(1)
        self.menuContext.showMenu()

    def makeDrink(self, drink, ingredients):
        """
        Main sequence to measure glass, scale recipe, confirm, and pour,
        with emergency-stop support.
        """
        self.emergency_stop = False
        if not self.check_sensors():
            self.led.clear_display()
            self.led.draw_text2(0, 20, "Place glass & retry", 2)
            self.led.display()
            time.sleep(2)
            return
        glass = self.detect_glass_type()
        if not glass:
            self.led.clear_display()
            self.led.draw_text2(0, 20, "Invalid glass!", 2)
            self.led.display()
            time.sleep(2)
            return
        cap    = SMALL_CAPACITY if glass == 'small' else LARGE_CAPACITY
        total  = sum(ingredients.values())
        scale  = cap / float(total)
        scaled = {ing: vol * scale for ing, vol in ingredients.items()}
        self.led.clear_display()
        self.led.draw_text2(0, 10, f"{glass.title()} glass", 2)
        self.led.draw_text2(0, 40, "Press Confirm", 1)
        self.led.display()
        self.wait_for_confirmation()
        if self.emergency_stop:
            return
        self.running = True
        maxTime    = 0
        threads    = []
        for ing, vol in scaled.items():
            for key in self.pump_configuration:
                if ing == self.pump_configuration[key]['value']:
                    t = vol * FLOW_RATE
                    maxTime = max(maxTime, t)
                    threads.append(threading.Thread(
                        target=self.pour,
                        args=(self.pump_configuration[key]['pin'], t)
                    ))
        for t in threads: t.start()
        self.progressBar(maxTime)
        for t in threads: t.join()
        self.menuContext.showMenu()
        self.running = False

    def left_btn(self, ctx):
        if not self.running:
            self.menuContext.advance()

    def right_btn(self, ctx):
        if not self.running:
            self.menuContext.select()

    def updateProgressBar(self, percent, x=15, y=15):
        height = 10
        width = SCREEN_WIDTH - 2*x
        for w in range(width):
            self.led.draw_pixel(w + x, y)
            self.led.draw_pixel(w + x, y + height)
        for h in range(height):
            self.led.draw_pixel(x, h + y)
            self.led.draw_pixel(x + width, h + y)
        fill_w = int(percent/100.0 * width)
        for w in range(fill_w):
            for h in range(height):
                self.led.draw_pixel(x + w, y + h)

    def wait_for_confirmation(self):
        while GPIO.input(self.btn_confirm):
            time.sleep(0.1)

    def prime_pumps(self):
        self.led.clear_display()
        self.led.draw_text2(0, 20, "Prime pumps? Press OK", 2)
        self.led.display()
        self.wait_for_confirmation()
        for p in self.pump_configuration:
            GPIO.output(self.pump_configuration[p]['pin'], GPIO.LOW)
        time.sleep(PRIME_TIME)
        for p in self.pump_configuration:
            GPIO.output(self.pump_configuration[p]['pin'], GPIO.HIGH)
        self.led.clear_display()
        self.led.draw_text2(0, 20, "Priming done", 2)
        self.led.display()
        time.sleep(2)

    def is_glass_present(self):
        return GPIO.input(IR_PIN) == 0

    def get_glass_weight(self):
        w = self.hx.get_weight(5)
        self.hx.power_down()
        self.hx.power_up()
        time.sleep(0.1)
        return w

    def detect_glass_type(self):
        w = self.get_glass_weight()
        if abs(w - SMALL_EMPTY_WT) < 50:
            return 'small'
        if abs(w - LARGE_EMPTY_WT) < 100:
            return 'large'
        return None

    def check_sensors(self):
        return self.is_glass_present() and (self.detect_glass_type() is not None)

    def run(self):
        self.prime_pumps()
        while True:
            size = self.detect_glass_type()
            if size:
                self.led.clear_display()
                self.led.draw_text2(0, 20, f"{size.title()} glass detected", 2)
                self.led.draw_text2(0, 50, "Press Confirm", 1)
                self.led.display()
                self.wait_for_confirmation()
                break
            else:
                self.led.clear_display()
                self.led.draw_text2(0, 20, "No glass detected", 2)
                self.led.draw_text2(0, 50, "Place glass", 1)
                self.led.display()
                time.sleep(1)
        self.startInterrupts()
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            GPIO.cleanup()
        GPIO.cleanup()

if __name__ == '__main__':
    bartender = Bartender()
    bartender.buildMenu(drink_list, drink_options)
    bartender.run()
