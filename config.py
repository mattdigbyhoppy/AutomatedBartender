# GPIO pin assignments
PUMP_PINS = {
    'rum': 17,    # BCM pin numbers for each fluid’s relay
    'coke': 27,
    'gin': 22,
    
}

# Priming durations (seconds) for each pump
PRIMING_TIME = {
    'rum': 5,
    'coke': 4,
    
}

# Sensor pins
IR_SENSOR_PIN = 23
# HX711 pins (weight sensor)
HX711_DT = 5
HX711_SCK = 6

# LCD resolution
SCREEN_SIZE = (320, 240)
