import time                  # Time utilities (sleep)
import sys                   # System utilities
import RPi.GPIO as GPIO      # Raspberry Pi GPIO library
import json                  # JSON parsing for config
import threading             # Threading for pump control
from luma.core.render import canvas
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from hx711 import HX711       # HX711 ADC driver for load cell
from menu import MenuItem, Menu, Back, MenuContext, MenuDelegate
from drinks import drink_list, drink_options

# Use BCM (Broadcom) pin numbering
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


# Display constants for the OLED
SCREEN_WIDTH    = 128       # OLED width in pixels
SCREEN_HEIGHT   = 64        # OLED height in pixels
OLED_RESET_PIN  = 15        # Reset pin for OLED (not used in luma)
OLED_DC_PIN     = 16        # Data/Command pin for OLED


# Pump flow rate: seconds needed to pour 1 mL
FLOW_RATE = 60.0 / 100.0     # 0.6 s per mL

# Sensor & button GPIO assignments (BCM)
IR_PIN       = 22  # IR break-beam sensor output
TORSION_DT   = 4   # HX711 data pin
TORSION_SCK  = 16  # HX711 clock pin
BTN_CONFIRM  = 12   # Confirm button
BTN_CANCEL   = 6   # Cancel button
BTN_MENU     = 5  # Menu navigation button
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

        # configure all buttons as inputs, pulled down
        for btn in (BTN_CONFIRM, BTN_CANCEL, BTN_MENU, BTN_SPECIAL):
            GPIO.setup(btn, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        # keep these for wait_for_confirmation()
        self.btn_confirm = BTN_CONFIRM
        self.btn_cancel  = BTN_CANCEL

        # initialize the last-seen state for polling
        self._last_state = {
            BTN_CONFIRM: GPIO.LOW,
            BTN_CANCEL:  GPIO.LOW,
            BTN_MENU:    GPIO.LOW,
            BTN_SPECIAL: GPIO.LOW
        }

        # --- Initialize the HX711 load-cell interface ---
        GPIO.setup(TORSION_DT, GPIO.IN)
        GPIO.setup(TORSION_SCK, GPIO.OUT)
        try:
            self.hx = HX711(
                dout_pin       = TORSION_DT,
                pd_sck_pin     = TORSION_SCK,
                gain_channel_A = 128,
                select_channel = 'A'
            )
            self.hx.reset()
            self.hx.zero()  # tare to zero
        except Exception as e:
            print(f"[WARNING] HX711 init/zero failed: {e}")
            self.hx = None

        # --- Initialize IR beam sensor ---
        GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Initialize the OLED via I2C
        serial = i2c(port=1, address=0x3D)
        self.led = ssd1306(serial, width=SCREEN_WIDTH, height=SCREEN_HEIGHT)
        self.led.clear()
        self.led.show()

        # --- Load pump config and set up relay outputs ---
        self.pump_configuration = Bartender.readPumpConfiguration()
        for pump in self.pump_configuration.values():
            GPIO.setup(pump['pin'], GPIO.OUT, initial=GPIO.HIGH)

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
            
    def pollButtons(self):
        """
        Poll each button once; on LOW?HIGH transition call its handler.
        """
        for pin, handler in (
            (BTN_CONFIRM, self.confirm_btn),
            (BTN_CANCEL,  self.emergency_stop_cb),
            (BTN_MENU,    self.next_btn),
            (BTN_SPECIAL, self.prev_btn),
        ):
            cur = GPIO.input(pin)
            if cur == GPIO.HIGH and self._last_state[pin] == GPIO.LOW:
                handler(pin)
            self._last_state[pin] = cur
       
                    
    def next_btn(self, channel):
        """GPIO callback for the MENU button ? move to next menu item."""
        print(f"[DEBUG] MENU button pressed (GPIO {channel})")
        if not self.running:
            self.menuContext.advance()

    def prev_btn(self, channel):
        """SPECIAL: move to the previous menu item."""
        print(f"[DEBUG] SPECIAL button pressed (GPIO {channel})")
        if not self.running:
            ctx = self.menuContext
            # cycle backwards through options
            menu = ctx.currentMenu
            menu.selectedOption = (menu.selectedOption - 1) % len(menu.options)
            ctx.display(menu.getSelection())
        
    def confirm_btn(self, channel):
        """
        GPIO callback for the CONFIRM button.
        
        """
        print(f"[DEBUG] CONFIRM button pressed (GPIO {channel})")
        if not self.running:
            self.menuContext.select()

    def buildMenu(self, drink_list, drink_options):
        """
        Build the hierarchical menu structure:
        - Top level: drinks + 'Settings'
        - Settings: submenus for each pump to select liquid
        """
        m = Menu("Main Menu")

        # 1) Add all drinks
        for d in drink_list:
            m.addOption(MenuItem('drink', d['name'], {'ingredients': d['ingredients']}))

        # 2) Add the settings submenu (was called 'Configure')
        settings = Menu('Settings')
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
            sub.setParent(settings)
            settings.addOption(sub)

        # 3) Keep the clean option
        settings.addOption(MenuItem('clean', 'Clean'))

        # 4) Finally tack it on
        m.addOption(settings)

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
        # self.filterDrinks(menu)
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
        with canvas(self.led) as draw:
            draw.text((0, 20), menuItem.name, fill="white")


    def pour(self, pin, wait):
        """
        Activate a pump relay (active LOW) for up to `wait` seconds,
        but abort immediately on emergency_stop.
        """
        GPIO.output(pin, GPIO.LOW)
        elapsed = 0.0
        step    = 0.1
        while elapsed < wait:
            # poll buttons to catch emergency-stop
            self.pollButtons()
            if self.emergency_stop:
                break

            time.sleep(step)
            elapsed += step

        GPIO.output(pin, GPIO.HIGH)


    def progressBar(self, waitTime, dispenses):
        """
        Draw a volume-based progress bar over `waitTime` seconds.
        `dispenses` is a list of (volume_mL, pour_time_s) for each pump.
        """
        glass_vol = sum(vol for vol, _ in dispenses)
        steps     = 100
        interval  = waitTime / steps

        for i in range(steps + 1):
            # allow emergency stop at any time
            self.pollButtons()
            if self.emergency_stop:
                break

            elapsed    = i * interval
            # sum up how much volume each pump has delivered so far
            delivered = sum(vol * min(elapsed, t) / t for vol, t in dispenses)
            pct        = delivered / glass_vol if glass_vol > 0 else 0.0

            with canvas(self.led) as draw:
                # header
                draw.text((0, 0), f"Pouring {int(glass_vol)} mL", fill="white")

                # bar
                x, y = 15, 20
                w    = SCREEN_WIDTH - 2*x
                h    = 10
                draw.rectangle((x, y, x+w, y+h), outline="white")
                fill_w = int(pct * w)
                draw.rectangle((x, y, x+fill_w, y+h), fill="white")

                # counter
                draw.text((0, y + h + 4),
                          f"{int(delivered)}/{int(glass_vol)} mL",
                          fill="white")

            time.sleep(interval)




    def emergency_stop_cb(self, channel):
        """
        Cancel button pressed → abort everything & return to main menu.
        """
        self.emergency_stop = True
        self.running = False
        with canvas(self.led) as draw:
            draw.text((0, 20), "!! EMERGENCY !!", fill="white")

        time.sleep(1)
        self.menuContext.showMenu()

    def makeDrink(self, drink, ingredients):
        """
        Main sequence to:
          0) wait for glass on the break-beam,
          1) let the user pick Shot (50 mL) or Regular (250 mL),
          2) confirm pour, and
          3) pour with emergency-stop support.
        """
        # Reset emergency flag
        self.emergency_stop = False

        # 0) Wait for glass
        with canvas(self.led) as draw:
            draw.text((0, 10), "Place glass to start", fill="white")
        while not self.is_glass_present():
            time.sleep(0.1)
        with canvas(self.led) as draw:
            draw.text((0, 10), "Glass detected!", fill="white")
        time.sleep(0.5)

        # 1) Glass-size picker
        options = [("Shot",     50.0),
                   ("Regular", 250.0)]
        sel = 1  # default to Regular
        while True:
            with canvas(self.led) as draw:
                draw.text((0,  5), "Select Glass Size", fill="white")
                draw.text((0, 25), f"< {options[sel][0]} >", fill="white")
                draw.text((0, 45), f"{int(options[sel][1])} mL", fill="white")

            if GPIO.input(BTN_MENU) == GPIO.HIGH:
                sel = (sel + 1) % 2
                time.sleep(0.2)
            elif GPIO.input(BTN_SPECIAL) == GPIO.HIGH:
                sel = (sel - 1) % 2
                time.sleep(0.2)
            elif GPIO.input(self.btn_confirm) == GPIO.HIGH:
                glass_vol = options[sel][1]
                break
            elif GPIO.input(self.btn_cancel) == GPIO.HIGH:
                self.emergency_stop = True
                return
            time.sleep(0.05)

        # 2) Scale recipe to chosen glass volume
        total = sum(ingredients.values())
        scale = glass_vol / float(total)
        scaled = {ing: vol * scale for ing, vol in ingredients.items()}

        # build a list of (volume, pour_time) for each pump
        dispenses = []
        max_time = 0.0
        for ing, vol in scaled.items():
            for key, p in self.pump_configuration.items():
                if ing == p['value']:
                    t = vol * FLOW_RATE
                    max_time = max(max_time, t)
                    dispenses.append((vol, t))

        # 3) Confirm pour
        with canvas(self.led) as draw:
            draw.text((0, 10), f"{options[sel][0]} glass", fill="white")
            draw.text((0, 40), "Press Confirm",   fill="white")
        self.wait_for_confirmation()
        if self.emergency_stop:
            return

        # 4) Fire pumps
        self.running = True
        threads = []
        for ing, vol in scaled.items():
            for key, p in self.pump_configuration.items():
                if ing == p['value']:
                    t = vol * FLOW_RATE
                    threads.append(threading.Thread(
                        target=self.pour, args=(p['pin'], t)
                    ))
        for thr in threads: thr.start()

        # 5) Show volume-based progress
        self.progressBar(max_time, dispenses)

        # 6) Wait for pumps to finish
        for thr in threads: thr.join()

        # 7) Back to menu
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
        """
        Block until the Confirm button goes HIGH, or until emergency_stop is triggered.
        """
        while GPIO.input(self.btn_confirm) == GPIO.LOW:
            # check for emergency button
            self.pollButtons()
            if self.emergency_stop:
                return
            time.sleep(0.1)

    def prime_pumps(self):
        """
        Run all pumps for PRIME_TIME seconds to prime tubing,
        with an on-screen status update.
        """
        # 1) Notify user that priming is starting
        with canvas(self.led) as draw:
            draw.text((0, 20), "Priming pumps...", fill="white")

        # 2) Activate all pumps (relays are active LOW)
        for pump in self.pump_configuration.values():
            GPIO.output(pump['pin'], GPIO.LOW)

        # 3) Let them run for PRIME_TIME seconds
        time.sleep(PRIME_TIME)

        # 4) Turn pumps off
        for pump in self.pump_configuration.values():
            GPIO.output(pump['pin'], GPIO.HIGH)

        # 5) Notify user that priming is done
        with canvas(self.led) as draw:
            draw.text((0, 20), "Priming done", fill="white")
        time.sleep(2)

    def is_glass_present(self):
        """
        Returns True when the IR beam is broken (glass is in place).
        Beam intact (no glass) ? GPIO HIGH
        Beam broken (glass present) ? GPIO LOW
        """
        return GPIO.input(IR_PIN) == GPIO.LOW


    
    def get_glass_weight(self):
        """
        Read and return the glass weight in grams, averaged over 5 samples.
        If the HX711 failed to initialize, or an error occurs,
        return 0.0 and log a warning.
        """
        if not self.hx:
            return 0.0

        try:
            return self.hx.get_weight_mean(readings=5)
        except Exception as e:
            print(f"[WARNING] HX711 read failed: {e}")
            return 0.0


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
        """
        1) Ask once whether to prime.
        2) Prime (or skip) on user choice.
        3) Immediately show drink menu.
        4) Poll buttons in a tight loop for navigation & selection.
        """
        # 1) Offer priming choice
        with canvas(self.led) as draw:
            draw.text((0, 20), "CONFIRM ? prime", fill="white")
            draw.text((0, 40), "CANCEL  ? skip",  fill="white")

        choice = None
        while choice is None:
            if GPIO.input(self.btn_confirm) == GPIO.HIGH:
                choice = True
            elif GPIO.input(self.btn_cancel) == GPIO.HIGH:
                choice = False
            time.sleep(0.05)

        # 2) Act on choice
        if choice:
            self.prime_pumps()

        # clear any leftover emergency flag
        self.emergency_stop = False

        # 3) Show the menu once
        self.menuContext.showMenu()

        # 4) Poll buttons forever
        try:
            while True:
                self.pollButtons()
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            GPIO.cleanup()







if __name__ == '__main__':
    bartender = Bartender()
    bartender.buildMenu(drink_list, drink_options)
    bartender.run()
