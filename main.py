#!/usr/bin/env python3

from utils import *
add_submodule_to_path() # bit of hacking ;)

import logging
import threading
import argparse
import traceback
import pickle

from bluezero import adapter
from bluezero.device import Device
from bluezero.central import Central

from log_manager import LogManager
LogManager.init(level=logging.DEBUG)

from pump_advertiser import PumpAdvertiser
from peripheral_handler import PeripheralHandler, BleService, BleChar
from sake_handler import SakeHandler

import datetime as dt
import importlib
import sys

DUMP_COUNT = 1000

pa:PumpAdvertiser = None
sh:SakeHandler = None
device:Device = None
pump = None

# Component instances
sgr = None
socpc = None
cgmm = None
certman = None
hr = None
hatss = None
devinf = None
iddstatus = None

# Actions dict
actions = {}

# HOW TO ADD A NEW MODULE:
# 1. Add global variable declaration at module level (e.g., new_component = None)
# 2. Add import in initialize_components() function
# 3. Instantiate in initialize_components() function
# 4. Add module name to modules_to_reload list in reload_modules()
# 5. Add unsubscribe call in unsubscribe_components()
# 6. Add action in setup_actions() function

def initialize_components(pump):

    global sgr, socpc, cgmm, certman, hr, hatss, devinf, dbm, iddstatus

    from sg_reader import SGReader
    from socp import SocpController
    from cgm_misc import CgmMiscData
    from cm import CertificateManagement
    from history_reader import HistoryReader
    from hats import HATS
    from device_info import DeviceInfo
    from database_manager import DatabaseManager
    from idd_status_reader import IDDStatusReader

    sgr = SGReader(pump)
    logging.info("sg reader created")
    socpc = SocpController(pump)
    logging.info("SocpController created")
    cgmm = CgmMiscData(pump)
    logging.info("CgmMiscData created")
    certman = CertificateManagement(pump)
    logging.info("CertificateManagement created")
    hr = HistoryReader(pump)
    logging.info("HistoryReader created")
    hatss = HATS(pump)
    logging.info("HATS created")
    devinf = DeviceInfo(pump)
    logging.info("DeviceInfo created")

    dbm = DatabaseManager(hr)
    logging.info("DatabaseManager created")

    iddstatus = IDDStatusReader(pump)
    logging.info("IDDStatusReader created")

    return    


def unsubscribe_components():

    global sgr, socpc, cgmm, certman, hr, hatss, devinf

    sgr.unsubscribe()
    socpc.unsubscribe()
    cgmm.unsubscribe()
    certman.unsubscribe()
    hr.unsubscribe()
    hatss.unsubscribe()
    devinf.unsubscribe()
    iddstatus.unsubscribe()

    return

def reload_modules():

    global actions, pump

    modules_to_reload = [
        'sg_reader',
        'socp',
        'cgm_misc',
        'cm',
        'history_reader',
        'hats',
        'device_info',
        'database_manager',
        'idd_status_reader',
    ]

    # We have to unsubscribe from the component's characteristic
    # notifications/indications before reloading. This will clear the
    # associated callbacks that would otherwise add up with every reload
    # because bluezero does not check for duplicate callbacks being added.
    #
    # Inside the component, call add_characteristic_cb(None) to clear the
    # callback.
    #
    # see https://github.com/ukBaz/python-bluezero/issues/342#issuecomment-894165954
    #
    # (That commit has since been merged into the bluezero codebase.)
    logging.info("Unsubscribing components...")
    unsubscribe_components()
        
    # Clear actions dict first to break closures holding references
    actions.clear()
    
    # Remove modules from sys.modules and reimport
    for mod_name in modules_to_reload:
        try:
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            importlib.import_module(mod_name)
            logging.info(f"Reloaded: {mod_name}")
        except Exception as e:
            logging.error(f"Reload failed for {mod_name}: {e}")
    
    # Reinitialize components and actions
    initialize_components(pump)
    setup_actions()
    logging.info("Components re-initialized")
    return

def print_help():
    print("\n\n" + "="*40)
    print("Available commands:")
    for k, (desc, _) in actions.items():
        print(f"  {k}: {desc}")
    return

def save_history():
    filename = dt.datetime.now().strftime("%Y-%m-%d__%H-%M-%S_history_data.txt")

    # get history data from pump
    records = hr.get_last_n_records(DUMP_COUNT)

    # write data to file as hexstring
    with open(filename, "w") as f:
        for r in records:
            f.write(r.raw_data.hex() + "\n")

def setup_actions():
    global actions
    
    actions = {
        'h': ('Show help/commands', lambda: print_help()),
        'r': ('Reload all modules', lambda: reload_modules()),

        '1': ('Read sensor glucose value', lambda: sgr.get_value()),
        '2': ('Read sensor details', lambda: socpc.read_sensor_details()),

        '3': ('Read CGM run time', lambda: cgmm.read_run_time()),
        '4': ('Read CGM start time', lambda: cgmm.read_start_time()),
        '5': ('Read CGM remaining time', lambda: cgmm.calc_remaining_time()),

        '6': ('Send certificate mgmt request', lambda: certman.send_request()),
        '7': ('Send HATS request', lambda: hatss.send_request()),

        '8': ('Read IDD History - record count', lambda: hr.get_available_record_count()),
        '9': ('Read IDD History - last record', lambda: hr.get_last_record()),
        '10': ('Read IDD History - first record', lambda: hr.get_first_record()),
        '11': ('Read IDD History - last 10 records', lambda: hr.get_last_n_records()),
    #    '12': (f'Save IDD history of {DUMP_COUNT} records to a file', lambda: save_history()),
        '12': (f'Sync all data to the database', lambda: dbm.sync()),
        '13': ('Read device info', lambda: devinf.get_device_info()),

        '14': ('Read IDD status - Get Time In Range', lambda: iddstatus.get_time_in_range()),
        '15': ('Read IDD status - Get Insulin On Board', lambda: iddstatus.get_insulin_on_board()),
        '16': ('Read IDD status - Get Therapy Algo States', lambda: iddstatus.get_therapy_algorithm_states()),

        '17': ('IDD status test all calls', lambda: iddstatus.test_all()),


    }

def main_input_loop():

    while True:
        print("\n> ", end='')
        key = input().strip().lower()
        if key in actions:
            try:
                actions[key][1]()
                print_help()
            except Exception as e:
                trace = traceback.print_exc()
                print(f"Action '{actions[key][0]}' failed: {e} {trace if trace is not None else ''}")
        elif key:
            print(f"Unknown key: {key}. Press 'h' for help.")

def main_logic():
    global sgr, socpc, cgmm, certman, hr, pump

    initialized = False

    while True:
        # dont waste cpu cycles
        sleep(0.1)
        
        # SAKE handshake must have been completed, wait for it
        if sh is None or not sh.is_done():
            continue

        # connection to pump must have been established and GATT discovery must have been completed
        if not device or not device.services_resolved:
            continue
        
        # initialize stuff if not already
        if not initialized:
            initialized = True
            assert device.services_resolved

            pump = Central(device.address, device.adapter)
            pump.load_gatt()

            initialize_components(pump)
            setup_actions()

            # Run main input loop
            print_help()
            main_input_loop()

def main():

    global ph, pa, sh, device

    # parse CLI args
    parser = argparse.ArgumentParser(description="Python Pump Connector")
    parser.add_argument('-p', '--advertise_paired',
                        help='Mobile name to use if this device has already been paired with a pump. In a format of 6 number digits.',
                        default=None)
    parser.add_argument('-a', '--adapter-address',
        help='MAC address of the Bluetooth adapter to use')
    parser.add_argument('--no-adv-interval-hack',
        action='store_true', default=False,
        help='Do not use the software hack to shorten the advertising interval on reconnects')
    args = parser.parse_args()

    # check if bt is even on
    if not is_bluetooth_active():
       raise Exception("you need to have bluetooth running!")
    
    if not bt_privacy_on():
        raise Exception("BT privacy does not seem to be on. You need to manually edit /etc/bluetooth/main.conf and add 'Privacy = device' under [General]. After that, restart the bluethoothd service and re-pair on your pump!")

    # ask for pw
    logging.warning("Enter sudo password if asked: (we need this for the low level btmgmt tool)")
    exec("sudo echo")

    if args.adapter_address:
        adapter_addr = args.adapter_address
    else:
        # use first Bluetooth adapter found
        adapter_addr = next(adapter.Adapter.available()).address

    sh = SakeHandler()
    ph = PeripheralHandler(adapter_addr)

    # if user did not provide an already-paired name, start from fresh
    if not args.advertise_paired:
        forget_pump_devices()
        mobile_name = None
        paired = False
    else:
        mobile_name = "Mobile " + args.advertise_paired
        paired = True

    pa = PumpAdvertiser(mobile_name, paired, use_adv_interval_hack=not args.no_adv_interval_hack)
    
    def on_connect(dev:Device):
        global device
        device = dev
        pa.on_connect_cb(dev)

    ph.set_on_connect(on_connect)
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

