# Imports
from machine import Pin, ADC, Timer
import math
import time

#######################################
# Pin and constant definitions
#######################################
adc_pin = ADC(0)  # ADC pin for reading voltage
buttonPin = Pin(16, Pin.IN, Pin.PULL_UP)  # Button pin with internal pull-up resistor

SEVEN_SEGMENT_START_PIN = 0  # Starting pin for the 7-segment display
DISPLAY_COUNT = 4  # Number of 7-segment displays
DECIMAL_PRECISION = 2  # Number of decimal places to display
voltage_value = 0  # Initial voltage value

# HEX values for 7-segment display digits (0-9, A-F, and empty)
digit_list_hex = [
    0x40,  # 0
    0x79,  # 1
    0x24,  # 2
    0x30,  # 3
    0x19,  # 4
    0x12,  # 5
    0x02,  # 6
    0x78,  # 7
    0x00,  # 8
    0x10,  # 9
    0x08,  # A
    0x03,  # b
    0x46,  # C
    0x21,  # d
    0x06,  # E
    0x0E,  # F
    0x7F   # Empty
]

#######################################
# Global variables
#######################################
display_value = 0  # Value to be displayed
last_button_time_stamp = 0  # Timestamp of the last button press
button_pressed = False  # Button pressed state

segment_pins = []  # List to hold segment pins
display_select_pins = []  # List to hold display select pins
current_display_index = DISPLAY_COUNT - 1  # Current display index for multiplexing
display_timer = None  # Timer for display multiplexing
counter_timer = None  # Timer for button press handling

#######################################
# Function definitions
#######################################

# Function to read the ADC pin and convert the digital value to a voltage level (0-3.3V)
def read_analogue_voltage(adcPin):
    adcValue = adcPin.read_u16()  # Read the ADC value (0-65535)
    max_voltage = 3.3  # Maximum voltage reference
    voltage = adcValue * (max_voltage / 65535)  # Convert ADC value to voltage
    milliVolt = voltage * 1000  # Convert voltage to millivolts
    return voltage, milliVolt

# Function to read the ADC pin and convert the digital value to a temprture level (-24-80C)
# Constants for the thermistor
BETA = 3950   # Beta parameter
R0 = 10000    # Resistance at 25 degrees Celsius (Ohms)
T0 = 25 + 273.15  # Reference temperature (Kelvin)

def get_temp(temp_sensor_pin):
    adc_value = temp_sensor_pin.read_u16()
    # Convert the ADC value to resistance
    R = 10000 / ((65535 / adc_value) - 1)
    
    # Calculate temperature in Kelvin
    temp_k = 1 / ((1 / T0) + (1 / BETA) * math.log(R / R0))
    
    # Convert Kelvin to Celsius
    temp_c = temp_k - 273.15
    
    return temp_c

# Function to disable the timer that triggers scanning of the 7-segment displays
def disable_display_timer():
    global display_timer
    display_timer.deinit()  # Disable the display timer

# Function to enable the timer that triggers scanning of the 7-segment displays
def enable_display_timer():
    global display_timer
    display_timer.init(period=30, mode=Timer.PERIODIC, callback=scan_display)  # Enable the display timer

# Function to handle scanning of the 7-segment displays
# Displays the value stored in the display_value global variable on available 7-segment displays
def scan_display(timer_int):
    global current_display_index, display_value

    # Extract the current digit
    digit = int((display_value // math.pow(10, current_display_index))) % 10
    # Display the digit and the decimal point if needed
    display_digit(digit, current_display_index, 
                  current_display_index == DECIMAL_PRECISION and 0 != DECIMAL_PRECISION)

    current_display_index = (current_display_index - 1)
    if current_display_index < 0:
        current_display_index = DISPLAY_COUNT - 1

# Function to display the given value on the display with the specified index
# dp_enable specifies if the decimal point should be on or off
def display_digit(digit_value, digit_index, dp_enable=False):
    if digit_value < 0 or digit_value > len(digit_list_hex) - 1:
        return

    for pin in display_select_pins:
        pin.value(0)  # Turn off all displays

    mask = digit_list_hex[digit_value]
    for i in range(7):
        segment_pins[i].value((mask >> i) & 1)  # Set the segment pins according to the digit mask

    segment_pins[7].value(0 if dp_enable else 1)  # Set the decimal point

    if digit_index == -1:
        for pin in display_select_pins:
            pin.value(1)  # Enable all displays (if index is -1)
    elif 0 <= digit_index < DISPLAY_COUNT:
        display_select_pins[digit_index].value(1)  # Enable the specific display

# Function to display the voltage value on the 7-segment displays
def display_voltage_value(value):
    disable_display_timer()  # Disable the display timer during update

    str_value = f"{value:.2f}"  # Convert the value to a string with 2 decimal places
    
    position = len(str_value) - 2  # Start position for displaying digits
    decimal_point_position = len(str_value) - str_value.index('.')  # Position of the decimal point

    for char in str_value:
        if char == '.':
            continue
        else:
            dp_enable = (position == decimal_point_position - 1)  # Enable decimal point if needed
            display_digit(int(char), position, dp_enable)  # Display the digit
            position -= 1

    enable_display_timer()  # Re-enable the display timer

# Interrupt handler for the button press
def irq_handler(pin):
    global button_pressed
    global last_button_time_stamp

    cur_button_ts = time.ticks_ms()  # Get the current timestamp
    button_press_delta = cur_button_ts - last_button_time_stamp  # Calculate the time difference

    if button_press_delta > 200:  # Debounce the button press
        last_button_time_stamp = cur_button_ts
        button_pressed = True  # Set the button pressed state

# Function to setup GPIO/ADC pins, timers, and interrupts
def setup():
    global button_pressed
    global segment_pins, display_select_pins
    global display_timer, counter_timer
    global display_value, voltage_value

    buttonPin.irq(trigger=Pin.IRQ_FALLING, handler=irq_handler)  # Set up the button interrupt

    # Set up the display select pins
    for i in range(SEVEN_SEGMENT_START_PIN + 8, SEVEN_SEGMENT_START_PIN + 8 + DISPLAY_COUNT):
        pin = Pin(i, Pin.OUT)
        pin.value(0)
        display_select_pins.append(pin)

    # Set up the segment pins
    for i in range(SEVEN_SEGMENT_START_PIN, SEVEN_SEGMENT_START_PIN + 8):
        pin = Pin(i, Pin.OUT)
        pin.value(1)
        segment_pins.append(pin)

    display_timer = Timer()
    enable_display_timer()  # Enable the display timer

    while True:
        if button_pressed:
            ## temprture ## uncomment this when using NTC 
            # temp = get_temp(adc_pin)
            # print(f"Tempreture: {temp:.2f}C")  # Print the voltage to the console
            
            ## voltage
            voltage, milliVolt = read_analogue_voltage(adc_pin)  # Read the voltage from the ADC
            voltage_value = voltage  # Update the global voltage value
            print(f"Voltage: {milliVolt:.2f}mV")  # Print the voltage to the console
            button_pressed = False  # Reset the button pressed state
        display_voltage_value(voltage_value)  # Update the display with the voltage value

if __name__ == '__main__':
    setup()  # Run the setup function to initialize the program
