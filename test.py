#!/usr/bin/env python3

from bluezero import peripheral, adapter, advertisement
from bluezero.broadcaster import Beacon

from threading import Thread
import os
from datetime import datetime
from time import sleep

import logging
from log_manager import LogManager

LogManager.init(level=logging.DEBUG)
from utils import *

add_submodule_to_path() # bit of hacking
from pysake.handshake_client import HandshakeClient




CONNECTED = False
MOBILE_NAME = None
BLE = None
SAKE_CHAR = None

def adv_thread():
    print("\n"*3)
    print("-"*10 + " starting advertisement!" + "-"*10)
    print(" "*10 + "(ignore error 0x0d)")
    while True:
        if not CONNECTED:
            advertise(MOBILE_NAME)
        sleep(0.1)

def send_sake_notif():
    zero = list(bytes.fromhex("00"*20))
    print("calling sake char set value...")
    SAKE_CHAR.set_value(zero)

def on_connect(dev):
    global CONNECTED
    CONNECTED = True
    print(f"Connected: {dev.address}")

def on_disconnect(adapter_addr, device_addr):
    global CONNECTED
    CONNECTED = False
    print(f"Disconnected {device_addr}, going back to advertising!")
    forget_pump_devices()

def read_callback():
    print("!!! READ")
    return [42,]

def notify_callback(notifying, char):
    print("!!! NOTIFY")
    print("Notifications:", "enabled" if notifying else "disabled")
    if notifying:
        # pump wants to be notified, start SAKE handshake
        send_sake_notif()

def write_callback(value, options):
    global buffer, characteristic
    print("!!! WRITE", value)


class PumpAdvertiser():

    mobile_name:str = None
    log:logging.Logger = None
    instance_id:int = None
    adv_started:datetime|None = None

    startup_commands:list[str] = [
        "sudo btmgmt power off",
        "sudo btmgmt bredr off",
        "sudo btmgmt le on",
        "sudo btmgmt sc off",
        "sudo btmgmt io-cap 3", # this is very important!
        "sudo btmgmt power on"
    ]

    def __init__(self, instance_id:int=1):
        """
        instance id is the bluez instance id
        """

        self.instance_id = instance_id
        self.logger = LogManager.get_logger(self.__class__.__name__)

        self.logger.info("Enter sudo password if asked: (we need this for the low level btmgmt tool)")
        exec("sudo echo 'Password entered'")

        # gen a mobile name
        self.mobile_name = gen_mobile_name()
        self.logger.info(f"generated mobile name: {self.mobile_name}")
        
        self.__adv_clear_internal() # just to be on the safe side

        # run btmgmt commands
        for c in self.startup_commands:
            exec(c)
            sleep(0.1) # wait for hci to actually perform it. NOTE: make this delay larger if you see errors!

        return

    def __create_adv_cmd(self, time) -> str:

        data = "02 01 06 "  # flags - we have turned BR/EDR off
        data += f"12 FF F901 00 {self.mobile_name.encode().hex()} 00 "  # manufacturer data
        data += "02 0A 01 "  # tx power
        data += "03 03 82 FE "  # 16-bit service UUID

        data = data.replace(" ", "")

        # timeout is how long the bluez object lives (??)
        # set duration and timeout to the same for now

        full_cmd = f"sudo btmgmt add-adv -d {data} -t {time} -D {time} {self.instance_id}"
        return full_cmd

    def __adv_clear_internal(self):
        exec("sudo btmgmt clr-adv")
        return

    def stop_adv(self) -> None:
        self.__adv_clear_internal()
        self.logger.info("advertising stopped")
        self.adv_started = None
        return

    def start_adv(self, duration:int=360) -> None:
        """
        time is in seconds
        """
        cmd = self.__create_adv_cmd(duration)
        exec(cmd)
        self.adv_started = datetime.now()
        self.logger.info(f"advertisement started at {self.adv_started}")
        return

def main():
    global MOBILE_NAME, BLE, SAKE_CHAR


    pa = PumpAdvertiser()
    pa.start_adv()

    print("\n\n")
    for i in range(5):
        print("ALWAYS ACCEPT THE PAIRING IF YOUR DESKTOP ENVIRONMENT SHOWS IT UP!")
    print("\n\n")

    forget_pump_devices()

    batch_exec(STARTUP_COMMANDS)    # configure the BT adapter

    adapter_addr = list(adapter.Adapter.available())[0].address
    print(f"using adapter: {adapter_addr}")

    BLE = peripheral.Peripheral(
        adapter_address=adapter_addr,
        local_name=MOBILE_NAME
    )

    sake_srv_id, sake_char_id = add_chars_and_services(BLE, write_callback, notify_callback, MOBILE_NAME)
    print(f"set up {len(BLE.services)} services and {len(BLE.characteristics)} chars ")

    SAKE_CHAR = None
    for char in BLE.characteristics:
        s, c = parse_id_from_path(char.path)
        if s == sake_srv_id and c == sake_char_id:
            SAKE_CHAR = char
            break
    if SAKE_CHAR == None:
        raise Exception("Could not find SAKE char!")
    print(f"sake char resolved to {SAKE_CHAR.path}")

    BLE.on_connect = on_connect
    BLE.on_disconnect = on_disconnect

    thread = Thread(target = adv_thread)
    thread.start()

    BLE.publish()
    
    return

if __name__ == "__main__":
    main()