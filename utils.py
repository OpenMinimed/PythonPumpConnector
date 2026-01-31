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

def parse_id_from_path(path: str) -> tuple[int, int]:
    """
    Extracts service and characteristic IDs from a Bluezero D-Bus path.

    Example:
        /ukBaz/bluezero/service0001/char0003  -> (1, 3)
    """
    parts = path.split('/')
    service_str = parts[-2]  # e.g., "service0001"
    char_str = parts[-1]     # e.g., "char0003"

    service_id = int(service_str.replace('service', ''))
    char_id = int(char_str.replace('char', ''))

    return (service_id, char_id)

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

def get_bluetooth_running() -> bool:
    result = subprocess.run(
        ["systemctl", "is-active", "bluetooth"],
        capture_output=True,
        text=True,
        check=True
    )
    status = result.stdout.strip()
    return status == "active" 
