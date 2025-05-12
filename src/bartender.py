import gaugette.ssd1306       # Driver for SSD1306 OLED display
import gaugette.platform     # Underlying platform interface
import gaugette.gpio         # GPIO interface for gaugette
import gaugette.spi          # SPI interface for gaugette
import time                  # Time utilities (sleep)
import sys                   # System utilities
import RPi.GPIO as GPIO      # Raspberry Pi GPIO library
import json                  # JSON parsing for config
import threading             # Threading for pump and light control
import traceback             # Tracebacks for error handling
from hx711 import HX711       # HX711 ADC driver for load cell
from dotstar import Adafruit_DotStar  # NeoPixel-style LED library
from menu import MenuItem, Menu, Back, MenuContext, MenuDelegate
from drinks import drink_list, drink_options

# Use BCM (Broadcom) pin numbering
GPIO.setmode(GPIO.BCM)

# Display constants for the OLED
SCREEN_WIDTH    = 128       # OLED width in pixels
SCREEN_HEIGHT   = 64        # OLED height in pixels
OLED_RESET_PIN  = 15        # Reset pin for OLED (not used in luma)
OLED_DC_PIN     = 16        # Data/Command pin for OLED

# NeoPixel (DotStar) configuration
NUMBER_NEOPIXELS    = 45    # Number of LEDs in the strip
NEOPIXEL_DATA_PIN   = 26    # Data pin for DotStar
NEOPIXEL_CLOCK_PIN  = 6     # Clock pin for DotStar
NEOPIXEL_BRIGHTNESS = 64    # Brightness (0-255)

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
        Initialize all hardware: buttons, sensors, display, pumps, LEDs
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
        # Use MSB byte order
        self.hx.set_reading_format("MSB", "MSB")
        # Set a 1:1 reference unit (tweak for calibration)
        self.hx.set_reference_unit(1)
        self.hx.reset()  # Clear any residual data
        self.hx.tare()   # Zero the scale with no weight

        # --- Initialize IR beam sensor ---
        # Pull-up keeps input HIGH until beam is broken
        GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # --- Initialize the OLED via SPI ---
        spi_bus    = 0
        spi_device = 0
        gpio_iface = gaugette.gpio.GPIO()         # GPIO abstraction
        spi_iface  = gaugette.spi.SPI(spi_bus, spi_device)  # SPI abstraction
        self.led   = gaugette.ssd1306.SSD1306(
            gpio_iface,
            spi_iface,
            reset_pin=OLED_RESET_PIN,
            dc_pin=OLED_DC_PIN,
            rows=SCREEN_HEIGHT,
            cols=SCREEN_WIDTH
        )
        self.led.begin()
        # Clear, invert (flash), then normal to show startup
        self.led.clear_display()
        self.led.invert_display()
        time.sleep(0.5)
        self.led.normal_display()
        time.sleep(0.5)

        # --- Load pump config and set up relay outputs ---
        self.pump_configuration = Bartender.readPumpConfiguration()
        for pump in self.pump_configuration:
            pin = self.pump_configuration[pump]["pin"]
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)  # Relays are active LOW

        # --- Initialize DotStar LED strip ---
        self.numpixels = NUMBER_NEOPIXELS
        self.strip = Adafruit_DotStar(
            self.numpixels,
            NEOPIXEL_DATA_PIN,
            NEOPIXEL_CLOCK_PIN
        )
        self.strip.begin()
        self.strip.setBrightness(NEOPIXEL_BRIGHTNESS)
        # Turn off all LEDs
        for i in range(self.numpixels):
            self.strip.setPixelColor(i, 0)
        self.strip.show()

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
        # Add each drink as a menu item
        for d in drink_list:
            m.addOption(MenuItem('drink', d['name'], {
                'ingredients': d['ingredients']
            }))
        # Build configuration submenu
        config = Menu('Configure')
        for p in sorted(self.pump_configuration.keys()):
            sub = Menu(self.pump_configuration[p]['name'])
            # Add each possible fluid option
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
                # Check if each ingredient matches a pump
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
        """
        Called by MenuContext before drawing: apply filters and selections.
        """
        self.filterDrinks(menu)
        self.selectConfigurations(menu)
        return True

    def menuItemClicked(self, menuItem):
        """
        Respond to menu selections:
        - Drinks: call makeDrink()
        - Pump selection: update config
        - Clean: call clean()
        """
        if menuItem.type == 'drink':
            self.makeDrink(
                menuItem.name,
                menuItem.attributes['ingredients']
            )
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
        # Create threads for each pump
        threads = []
        for p in self.pump_configuration:
            pin = self.pump_configuration[p]['pin']
            threads.append(threading.Thread(
                target=self.pour, args=(pin, wait)
            ))
        for t in threads:
            t.start()
        self.progressBar(wait)
        for t in threads:
            t.join()
        self.menuContext.showMenu()
        time.sleep(2)
        self.running = False

    def displayMenuItem(self, menuItem):
        """
        Render the currently selected menu item name on the OLED.
        """
        self.led.clear_display()
        self.led.draw_text2(0, 20, menuItem.name, 2)
        self.led.display()

    def cycleLights(self):
        """
        Animate a chasing light pattern on the DotStar strip.
        """
        t = threading.currentThread()
        head, tail, color = 0, -10, 0xFF0000
        while getattr(t, 'do_run', True):
            self.strip.setPixelColor(head, color)
            self.strip.setPixelColor(tail, 0)
            self.strip.show()
            time.sleep(1.0 / 50)
            head = (head + 1) % self.numpixels
            tail = (tail + 1) % self.numpixels
            if tail == 0:
                color = (color >> 8) or 0xFF0000

    def lightsEndingSequence(self):
        """
        Flash all LEDs green, then turn them off.
        """
        for i in range(self.numpixels):
            self.strip.setPixelColor(i, 0x00FF00)
        self.strip.show()
        time.sleep(2)
        for i in range(self.numpixels):
            self.strip.setPixelColor(i, 0)
        self.strip.show()

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
        # Clear display with message
        self.led.clear_display()
        self.led.draw_text2(0, 20, "!! EMERGENCY !!", 2)
        self.led.display()
        time.sleep(1)
        # Show main menu
        self.menuContext.showMenu()


    def makeDrink(self, drink, ingredients):
        """
        Main sequence to measure glass, scale recipe, confirm, and pour,
        with emergency-stop support.
        """
        # Reset emergency flag at start
        self.emergency_stop = False

        # 1) Ensure sensor health and presence
        if not self.check_sensors():
            self.led.clear_display()
            self.led.draw_text2(0, 20, "Place glass & retry", 2)
            self.led.display()
            time.sleep(2)
            return

        # 2) Identify glass size
        glass = self.detect_glass_type()
        if not glass:
            self.led.clear_display()
            self.led.draw_text2(0, 20, "Invalid glass!", 2)
            self.led.display()
            time.sleep(2)
            return

        # 3) Scale ingredients to glass capacity
        cap    = SMALL_CAPACITY if glass == 'small' else LARGE_CAPACITY
        total  = sum(ingredients.values())
        scale  = cap / float(total)
        scaled = {ing: vol * scale for ing, vol in ingredients.items()}

        # 4) Prompt user to confirm pouring
        self.led.clear_display()
        self.led.draw_text2(0, 10, f"{glass.title()} glass", 2)
        self.led.draw_text2(0, 40, "Press Confirm", 1)
        self.led.display()
        self.wait_for_confirmation()

        # If emergency stop pressed at confirmation, abort
        if self.emergency_stop:
            return

        # 5) Start pour animation and threads
        self.running = True
        lightsThread = threading.Thread(target=self.cycleLights)
        lightsThread.start()

        maxTime    = 0
        threads    = []
        for ing, vol in scaled.items():
            for key in self.pump_configuration:
                if ing == self.pump_configuration[key]["value"]:
                    t = vol * FLOW_RATE
                    maxTime = max(maxTime, t)
                    threads.append(threading.Thread(
                        target=self.pour,
                        args=(self.pump_configuration[key]["pin"], t)
                    ))

        for t in threads:
            t.start()

        # 6) Show progress (will break early on emergency_stop)
        self.progressBar(maxTime)

        # Ensure all pump threads finish (or abort)
        for t in threads:
            t.join()

        # 7) Cleanup lights and return to menu
        lightsThread.do_run = False
        lightsThread.join()

        # Even if emergency_stop occurred, return to main menu
        self.menuContext.showMenu()

        # Final reset
        self.running = False


    def left_btn(self, ctx):
        """
        Menu navigation: move to next option.
        """
        if not self.running:
            self.menuContext.advance()

    def right_btn(self, ctx):
        """
        Menu navigation: select current option.
        """
        if not self.running:
            self.menuContext.select()

    def updateProgressBar(self, percent, x=15, y=15):
        """
        Draw a rectangular progress bar at (x,y) based on percent.
        """
        height = 10
        width = SCREEN_WIDTH - 2*x
        # Draw border
        for w in range(width):
            self.led.draw_pixel(w + x, y)
            self.led.draw_pixel(w + x, y + height)
        for h in range(height):
            self.led.draw_pixel(x, h + y)
            self.led.draw_pixel(x + width, h + y)
        # Fill interior based on percent
        fill_w = int(percent/100.0 * width)
        for w in range(fill_w):
            for h in range(height):
                self.led.draw_pixel(x + w, y + h)

    def wait_for_confirmation(self):
        """
        Block until the confirm button is pressed.
        """
        while GPIO.input(self.btn_confirm):
            time.sleep(0.1)

    def prime_pumps(self):
        """
        Run all pumps for PRIME_TIME seconds to prime tubing.
        """
        self.led.clear_display()
        self.led.draw_text2(0, 20, "Prime pumps? Press OK", 2)
        self.led.display()
        self.wait_for_confirmation()
        # Turn all relays ON (LOW)
        for p in self.pump_configuration:
            GPIO.output(self.pump_configuration[p]['pin'], GPIO.LOW)
        time.sleep(PRIME_TIME)
        # Turn all relays OFF (HIGH)
        for p in self.pump_configuration:
            GPIO.output(self.pump_configuration[p]['pin'], GPIO.HIGH)
        self.led.clear_display()
        self.led.draw_text2(0, 20, "Priming done", 2)
        self.led.display()
        time.sleep(2)

    def is_glass_present(self):
        """
        Return True if the IR beam is broken (glass in place).
        """
        return GPIO.input(IR_PIN) == 0

    def get_glass_weight(self):
        """
        Read average weight from HX711.
        """
        w = self.hx.get_weight(5)
        self.hx.power_down()
        self.hx.power_up()
        time.sleep(0.1)
        return w

    def detect_glass_type(self):
        """
        Compare weight to thresholds to return 'small' or 'large'.
        """
        w = self.get_glass_weight()
        if abs(w - SMALL_EMPTY_WT) < 50:
            return 'small'
        if abs(w - LARGE_EMPTY_WT) < 100:
            return 'large'
        return None

    def check_sensors(self):
        """
        Return True only if glass present and weight reading valid.
        """
        return self.is_glass_present() and (self.detect_glass_type() is not None)

    def run(self):
        """
        Main loop: prime pumps, detect glass, then start menu navigation.
        """
        # Prime the lines
        self.prime_pumps()

        # Await valid glass detection and user confirmation
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

        # Enable menu button interrupts
        self.startInterrupts()
        try:
            while True:
                time.sleep(0.1)  # Idle loop
        except KeyboardInterrupt:
            GPIO.cleanup()
        GPIO.cleanup()


if __name__ == '__main__':
    # Instantiate and launch the bartender
    bartender = Bartender()
    bartender.buildMenu(drink_list, drink_options)
    bartender.run()
