import ctypes
import time
import threading
import subprocess

user32 = ctypes.windll.user32

# Constants for virtual keys
VK_LBUTTON = 0x01  # Left mouse button

# Track times
last_mouse_click_time = time.time()
last_keyboard_input_time = time.time()

# Define the executable to monitor
EXECUTABLE_NAME = "wmplayer.exe"


def get_process_cpu_usage(executable_name):
    try:
        # Get process list using WMIC (Windows XP compatible)
        output = subprocess.check_output(
            "wmic process where name='{}' get KernelModeTime,UserModeTime".format(executable_name),
            shell=True
        )
        lines = output.decode().splitlines()

        # Extract relevant values from WMIC output
        total_time = 0
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                total_time += int(parts[0]) + int(parts[1])

        return total_time
    except Exception:
        return None


def input_watcher():
    """Monitors both mouse and keyboard inputs in a single thread."""
    global last_mouse_click_time, last_keyboard_input_time
    prev_mouse_state = 0
    prev_keys = [0] * 256

    while True:
        now = time.time()

        # Check mouse click
        mouse_state = user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000
        if mouse_state and not prev_mouse_state:
            last_mouse_click_time = now
        prev_mouse_state = mouse_state

        # Check keyboard input
        for key_code in range(8, 256):  # Valid key range
            key_state = user32.GetAsyncKeyState(key_code) & 0x8000
            if key_state and not prev_keys[key_code]:
                last_keyboard_input_time = now
            prev_keys[key_code] = key_state

        time.sleep(0.01)  # Poll frequently without excessive CPU usage


def main():
    print("Monitoring {} CPU usage and input activity... (Press Ctrl+C to stop)".format(EXECUTABLE_NAME))

    prev_time = get_process_cpu_usage(EXECUTABLE_NAME)
    prev_sys_time = time.time()

    if prev_time is None:
        print("{} is not running.".format(EXECUTABLE_NAME))
        return

    while True:
        time.sleep(1)

        now = time.time()
        seconds_since_mouse = int(now - last_mouse_click_time)
        seconds_since_keyboard = int(now - last_keyboard_input_time)

        current_time = get_process_cpu_usage(EXECUTABLE_NAME)
        current_sys_time = time.time()

        if current_time is None:
            print("{} is not running.".format(EXECUTABLE_NAME))
            break

        elapsed_sys_time = current_sys_time - prev_sys_time
        cpu_usage = (current_time - prev_time) / (elapsed_sys_time * 100000)  # Convert to percentage

        print(
            "CPU Usage: {:<5} % | Seconds since last mouse click: {:<4} | Seconds since last keyboard input: {:<4}".format(
                round(cpu_usage, 2), seconds_since_mouse, seconds_since_keyboard
            ))

        prev_time = current_time
        prev_sys_time = current_sys_time


if __name__ == '__main__':
    threading.Thread(target=input_watcher, daemon=True).start()

    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
