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


class CDMonitor:
    def __init__(self):
        self.EXECUTABLE_NAME = "wmplayer.exe"
        self.WATCH_CPU_USAGE_CHECK_INTERVAL_SECONDS = 3
        self.MAX_CONSECUTIVE_IDENTICAL_CPU_READINGS = 10
        self.watch_cpu_usage = True
        self.cpu_usage_records = []

    def kill_existing_process(self):
        """Kills the executable if it is already running and waits 3 seconds if killed."""
        try:
            output = subprocess.check_output("tasklist", shell=True).decode("utf-8", errors="ignore")
            if self.EXECUTABLE_NAME.lower() in output.lower():
                logging.info("{} is already running. Terminating...".format(self.EXECUTABLE_NAME))
                subprocess.call("taskkill /F /IM {}".format(self.EXECUTABLE_NAME), shell=True)
                time.sleep(3)
                logging.info("{} terminated successfully.".format(self.EXECUTABLE_NAME))
            else:
                logging.info("{} is not running at script startup.".format(self.EXECUTABLE_NAME))
        except Exception as e:
            logging.error("Error while checking/killing {}: {}".format(self.EXECUTABLE_NAME, e))

    def get_process_cpu_usage(self):
        """Returns the CPU usage of the given process, or None if not found."""
        try:
            process = subprocess.Popen(
                "wmic process where name='{}' get KernelModeTime,UserModeTime".format(self.EXECUTABLE_NAME),
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = process.communicate(timeout=2)
            output = output.decode("utf-8", errors="ignore")
            lines = output.splitlines()
            if len(lines) < 2:
                logging.warning("Unexpected WMIC output: {}".format(output))
                return None
            total_time = 0
            for line in lines[1:]:
                parts = line.strip().split()
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    total_time += int(parts[0]) + int(parts[1])
            return total_time
        except subprocess.TimeoutExpired:
            logging.error("WMIC command timed out while checking CPU usage for {}".format(self.EXECUTABLE_NAME))
            return None
        except Exception as e:
            logging.error("Error getting CPU usage for {}: {}".format(self.EXECUTABLE_NAME, e))
            return None

    def detect_cd_drives(self):
        """Returns a list of drive letters for all detected CD/DVD drives."""
        cd_drives = []
        try:
            process = subprocess.Popen(
                "wmic cdrom get drive",
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, error = process.communicate()
            lines = output.decode("utf-8", errors="ignore").splitlines()
            for line in lines[1:]:  # Skip the header
                drive_letter = line.strip()
                if drive_letter and len(drive_letter) == 2 and drive_letter[1] == ":":
                    cd_drives.append(drive_letter[0])
        except Exception as e:
            logging.error("Error detecting CD/DVD drives: {}".format(e))
        return cd_drives

    def toggle_listener(self):
        """Listens for the ENTER key to toggle CPU usage monitoring."""
        while True:
            input()  # Wait for ENTER key press
            self.watch_cpu_usage = not self.watch_cpu_usage
            if self.watch_cpu_usage:
                logging.info("Resuming CPU usage monitoring.")
            else:
                logging.info("Pausing CPU usage monitoring. Clearing CPU usage records.")
                self.cpu_usage_records = []  # Clear records when paused

    def run_wmplayer_on_cd(self, drive_letter):
        """Launches the media player for the given CD drive and monitors CPU usage."""
        logging.info("Starting {} for CD in drive {}:\\".format(self.EXECUTABLE_NAME, drive_letter))
        command = 'start "" "{}" /device:AudioCD "{}:\\"'.format(self.EXECUTABLE_NAME, drive_letter)
        try:
            process = subprocess.Popen(command, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
            logging.info("Started {} for drive {}:\\".format(self.EXECUTABLE_NAME, drive_letter))
        except Exception as e:
            logging.error("Failed to start {}: {}".format(self.EXECUTABLE_NAME, e))
            return

        time.sleep(5)  # Allow wmplayer to start
        logging.info("Monitoring CPU usage. Press ENTER to toggle monitoring (currently enabled).")

        while True:
            if not self.watch_cpu_usage:
                time.sleep(self.WATCH_CPU_USAGE_CHECK_INTERVAL_SECONDS)
                continue

            cpu_usage = self.get_process_cpu_usage()
            if cpu_usage is None:
                logging.info("{} is no longer running. Moving to next CD drive.".format(self.EXECUTABLE_NAME))
                return

            self.cpu_usage_records.append(cpu_usage)
            if len(self.cpu_usage_records) > self.MAX_CONSECUTIVE_IDENTICAL_CPU_READINGS:
                self.cpu_usage_records.pop(0)
            logging.info("CPU Usage: {}".format(round(cpu_usage / 100000, 2)))

            # If the last MAX_CONSECUTIVE_IDENTICAL_CPU_READINGS CPU usage readings are identical, assume the CD has finished.
            if len(self.cpu_usage_records) == self.MAX_CONSECUTIVE_IDENTICAL_CPU_READINGS and len(set(self.cpu_usage_records)) == 1:
                logging.info("CD in drive {}:\\ appears to have finished playing. Terminating {}.".format(
                    drive_letter, self.EXECUTABLE_NAME))
                subprocess.call("taskkill /F /IM {}".format(self.EXECUTABLE_NAME), shell=True)
                time.sleep(5)
                return

            time.sleep(self.WATCH_CPU_USAGE_CHECK_INTERVAL_SECONDS)

    def run(self):
        """Main routine to manage CD playback across detected drives."""
        self.kill_existing_process()
        logging.info("Detecting CD/DVD drives...")
        cd_drives = self.detect_cd_drives()
        if not cd_drives:
            logging.info("No CD/DVD drives detected. Exiting early.")
            return
        logging.info(
            "Detected {} CD/DVD drives. Starting to play using drives: {}".format(len(cd_drives), ", ".join(cd_drives)))
        for drive in cd_drives:
            self.run_wmplayer_on_cd(drive)
        logging.info("Finished playing all {} CDs.".format(len(cd_drives)))


if __name__ == '__main__':
    monitor = CDMonitor()
    threading.Thread(target=monitor.toggle_listener, daemon=True).start()
    try:
        monitor.run()
    except KeyboardInterrupt:
        logging.info("Exiting...")
