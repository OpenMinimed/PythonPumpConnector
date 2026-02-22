#!/usr/bin/env python3

from utils import *
add_submodule_to_path() # bit of hacking ;)

import logging
import threading
import argparse

from log_manager import LogManager
LogManager.init(level=logging.DEBUG)

from pump_advertiser import PumpAdvertiser
from peripheral_handler import PeripheralHandler, BleService, BleChar
from sake_handler import SakeHandler

ph:PeripheralHandler = None
pa:PumpAdvertiser = None
sh:SakeHandler = None

def main_logic():

    first = True

    while True:

        sleep(0.1)
        
        if sh is None or not sh.is_done():
            continue
    
        if first:
            logging.info("welcome from the main logic!")
            first = False

        # TODO: put some ipython here for testing or something
    

def main():

    # parse CLI args
    parser = argparse.ArgumentParser(description="Python Pump Connector")
    parser.add_argument('-p', '--advertise_paired',
                        help='Mobile name to use if this device has already been paired with a pump. In a format of 6 number digits.',
                        default=None)
    args = parser.parse_args()

    # check if bt is even on
    if not is_bluetooth_active():
       raise Exception("you need to have bluetooth running!")

    # ask for pw
    logging.warning("Enter sudo password if asked: (we need this for the low level btmgmt tool)")
    exec("sudo echo")

    sh = SakeHandler()
    ph = PeripheralHandler()

    # if user did not provide an already-paired name, start from fresh
    if not args.advertise_paired:
        forget_pump_devices()
        mobile_name = None
        paired = False
    else:
        mobile_name = "Mobile " + args.advertise_paired
        paired = True

    pa = PumpAdvertiser(mobile_name, paired)
    
    ph.set_on_connect(pa.on_connect_cb)
    ph.set_on_disconnect(pa.on_disconnect_cb)

    # create the services
    service_info_serv = BleService("00000900-0000-1000-0000-009132591325", "Device Info")
    sake_serv = BleService("FE82", "Sake Service")
    ph.add_service(service_info_serv)
    ph.add_service(sake_serv)

    # create the characteristics
    mn = BleChar("2A29", "Manufacturer Name", "Google")
    mn_model = BleChar("2A24", "Model Number", "Nexus 5x")
    sn = BleChar("2A25", "Serial Number", "12345678")
    hw_rev = BleChar("2A27", "Hardware Revision", "HW 1.0")
    fw_rev = BleChar("2A26", "Firmware Revision", "FW 1.0")
    sw_rev = BleChar("2A28", "Software Revision", "2.9.0 f1093d1") # actual application version with commit hash
    system_id = BleChar("2A23", "System ID", bytes(8))
    pnp_id = BleChar("2A50", "PNP ID", bytes(7))
    cert_data = BleChar("2A2A", "Certification Data List", bytes(0))
    sake_port = BleChar("0000FE82-0000-1000-0000-009132591325", "Sake Port", None, sh.notify_callback, sh.write_callback)


    # add all chars
    for char in [mn, mn_model, sn, hw_rev, fw_rev, sw_rev, system_id, pnp_id, cert_data]:
        ph.add_char(service_info_serv, char)
    ph.add_char(sake_serv, sake_port)
   
    # finally before calling bluezero, start our advertisement and main logic thread
    pa.start_adv()

    logic_thread = threading.Thread(
        target=main_logic,
        name="logic_thread",
        daemon=True,
    )
    logic_thread.start()

    ph.publish()

    return

if __name__ == "__main__":
    main()