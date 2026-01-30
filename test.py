#!/usr/bin/env python3

from bluezero import peripheral, adapter, advertisement
from bluezero.broadcaster import Beacon

from threading import Thread
import os

import logging
from log_manager import LogManager

LogManager.init(level=logging.DEBUG)
from utils import *

add_submodule_to_path() # bit of hacking ;)
from pysake.handshake_client import HandshakeClient

from pump_advertiser import PumpAdvertiser


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



def main():
    global MOBILE_NAME, BLE, SAKE_CHAR

    # check if bt is even on
    if not get_bluetooth_running():
        raise Exception("you need to have bluetooth running using systemctl!")

    # ask for pw
    logging.warning("Enter sudo password if asked: (we need this for the low level btmgmt tool)")
    exec("sudo echo")

    # for now we need this hack, since if we did not create a sake connection, the device will forget it but our pc will not
    forget_pump_devices()

    # create an advertiser and start it
    pa = PumpAdvertiser()
    pa.start_adv()


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