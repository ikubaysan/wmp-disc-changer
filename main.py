import ctypes
import time
import threading
import subprocess
import logging
import os

# Configure logging with timestamps
logging.basicConfig(
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO
)

user32 = ctypes.windll.user32

# Constants for virtual keys
VK_LBUTTON = 0x01  # Left mouse button

# Track last input times
last_mouse_click_time = time.time()
last_keyboard_input_time = time.time()

# Executable to monitor
EXECUTABLE_NAME = "wmplayer.exe"


def kill_existing_process():
    """Kills the executable if it is already running and waits 3 seconds if killed."""
    try:
        # Check if the process is running
        output = subprocess.check_output("tasklist", shell=True).decode("utf-8", errors="ignore")
        if EXECUTABLE_NAME.lower() in output.lower():
            logging.info("{} is already running. Terminating...".format(EXECUTABLE_NAME))
            subprocess.call("taskkill /F /IM {}".format(EXECUTABLE_NAME), shell=True)
            time.sleep(3)  # Wait after termination
            logging.info("{} terminated successfully.".format(EXECUTABLE_NAME))
        else:
            logging.info("{} is not running at script startup.".format(EXECUTABLE_NAME))
    except Exception as e:
        logging.error("Error while checking/killing {}: {}".format(EXECUTABLE_NAME, e))


def get_process_cpu_usage():
    """Returns the CPU usage of the given process."""
    try:
        output = subprocess.check_output(
            "wmic process where name='{}' get KernelModeTime,UserModeTime".format(EXECUTABLE_NAME),
            shell=True
        )
        lines = output.decode().splitlines()
        total_time = 0
        for line in lines[1:]:
            parts = line.strip().split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                total_time += int(parts[0]) + int(parts[1])
        return total_time
    except Exception:
        return None


def detect_cd_drives():
    """Returns a list of drive letters for all detected CD/DVD drives."""
    cd_drives = []
    try:
        output = subprocess.check_output("wmic cdrom get drive", shell=True).decode().splitlines()
        for line in output[1:]:  # Skip header
            drive_letter = line.strip()
            if drive_letter and len(drive_letter) == 2 and drive_letter[1] == ":":
                cd_drives.append(drive_letter[0])  # Extract just the letter
    except Exception:
        pass
    return cd_drives


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


def run_wmplayer_on_cd(drive_letter):
    """Launches the media player for the given CD drive and monitors activity."""
    logging.info("Starting {} for CD in drive {}:\\".format(EXECUTABLE_NAME, drive_letter))

    # Use cmd.exe to launch wmplayer in the background properly
    command = 'start "" "{}" /device:AudioCD "{}:\\"'.format(EXECUTABLE_NAME, drive_letter)

    process = subprocess.Popen(command, shell=True)

    logging.info("Started {} for drive {}:\\".format(EXECUTABLE_NAME, drive_letter))

    time.sleep(5)  # Allow wmplayer to start

    while True:
        start_time = time.time()
        cpu_usage_records = []

        while time.time() - start_time < 10:  # Monitor CPU usage for 10 seconds
            cpu_usage = get_process_cpu_usage()
            now = time.time()
            seconds_since_mouse = int(now - last_mouse_click_time)
            seconds_since_keyboard = int(now - last_keyboard_input_time)

            if cpu_usage is None:
                logging.info("{} is no longer running. Moving to next CD drive.".format(EXECUTABLE_NAME))
                return

            cpu_usage_records.append(cpu_usage)
            logging.info("CPU Usage: {} | No input for {}s (mouse), {}s (keyboard)".format(
                round(cpu_usage / 100000, 2), seconds_since_mouse, seconds_since_keyboard
            ))

            time.sleep(1)  # Check every second

        # Determine if the CD has finished playing
        if len(set(cpu_usage_records)) == 1 and seconds_since_mouse >= 10 and seconds_since_keyboard >= 10:
            logging.info("CD in drive {}:\\ appears to have finished playing. Terminating {}.".format(
                drive_letter, EXECUTABLE_NAME))
            subprocess.call("taskkill /F /IM {}".format(EXECUTABLE_NAME), shell=True)
            time.sleep(5)  # Wait before moving to the next CD
            return


def main():
    # Kill any existing process before starting
    kill_existing_process()

    logging.info("Detecting CD/DVD drives...")
    cd_drives = detect_cd_drives()

    if not cd_drives:
        logging.info("No CD/DVD drives detected. Exiting early.")
        return

    logging.info("Detected {} CD/DVD drives. Starting to play using drives: {}".format(len(cd_drives), ", ".join(cd_drives)))

    for drive in cd_drives:
        run_wmplayer_on_cd(drive)
    logging.info("Finished playing all {} CDs.".format(len(cd_drives)))


if __name__ == '__main__':
    threading.Thread(target=input_watcher, daemon=True).start()

    try:
        main()
    except KeyboardInterrupt:
        logging.info("Exiting...")
