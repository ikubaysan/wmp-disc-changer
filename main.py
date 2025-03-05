import ctypes
import time
import threading

user32 = ctypes.windll.user32

# Constants for virtual keys
VK_LBUTTON = 0x01  # Left mouse button

# Track times
last_mouse_click_time = time.time()
last_keyboard_input_time = time.time()

def mouse_click_watcher():
    global last_mouse_click_time
    prev_state = 0
    while True:
        # Detect left mouse click state
        state = user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000
        if state and not prev_state:
            last_mouse_click_time = time.time()
        prev_state = state
        time.sleep(0.01)  # Poll frequently but don't use too much CPU

def keyboard_watcher():
    global last_keyboard_input_time
    prev_keys = [0]*256
    while True:
        for key_code in range(8, 256):  # valid key range
            key_state = user32.GetAsyncKeyState(key_code) & 0x8000
            if key_state and not prev_keys[key_code]:
                last_keyboard_input_time = time.time()
            prev_keys[key_code] = key_state
        time.sleep(0.01)  # Poll frequently but don't use too much CPU

if __name__ == '__main__':
    threading.Thread(target=mouse_click_watcher, daemon=True).start()
    threading.Thread(target=keyboard_watcher, daemon=True).start()

    print("Monitoring input (Press Ctrl+C to exit)...")
    start_time = time.time()
    try:
        while True:
            now = time.time()
            seconds_since_mouse = int(now - last_mouse_click_time)
            seconds_since_keyboard = int(now - last_keyboard_input_time)

            print("Seconds since last mouse click: {:<4} | Seconds since last keyboard input: {:<4}".format(
                seconds_since_mouse, seconds_since_keyboard))

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
