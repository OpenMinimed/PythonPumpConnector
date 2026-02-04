import random
import subprocess
from time import sleep
import sys
import os
import logging

def add_submodule_to_path():
    d = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(d, "PythonSake")
    if not os.path.isdir(d):
        raise FileNotFoundError(f"you are missing the submodule checkout! please fix")
    sys.path.append(d)
    logging.debug(f"{d} was added to path")
    return

def gen_mobile_name():
    while True:
        num = random.randint(100000, 999999)
        if num % 2 == 1:
            return f"Mobile {num}"

def exec(cmd:str) -> None:
    logging.debug(f"executing: {cmd}")
    subprocess.run(cmd, shell=True)
    return

def forget_pump_devices() -> None:
    """
    Forget all paired Bluetooth devices whose name starts with "Pump".
    Uses bluetoothctl CLI.
    """
    try:
        # Get list of paired devices
        result = subprocess.run(
            ['bluetoothctl', 'devices', 'Paired'],
            capture_output=True,
            text=True,
            check=True
        )
        lines = result.stdout.splitlines()

        for line in lines:
            # Format: Device XX:XX:XX:XX:XX:XX DeviceName
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                continue
            mac, name = parts[1], parts[2]
            if name.startswith("Pump"):
                logging.debug(f"Removing pairing for {name} ({mac})")
                subprocess.run(['bluetoothctl', 'remove', mac], check=False)

    except subprocess.CalledProcessError as e:
        logging.error(f"Error running bluetoothctl: {e}")
    return

import subprocess

def is_bluetooth_active() -> bool:
    # Check if bluetoothd is running
    proc = subprocess.run(
        ["pidof", "bluetoothd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if proc.returncode != 0:
        return False  # daemon not running

    # Check if systemd service is active
    result = subprocess.run(
        ["systemctl", "is-active", "bluetooth"],
        capture_output=True,
        text=True
    )

    return result.returncode == 0 and result.stdout.strip() == "active"
