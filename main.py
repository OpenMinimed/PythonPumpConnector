#!/usr/bin/env python3

from utils.os_utils import *
add_submodule_to_path() # bit of hacking ;)

import logging
import threading
import argparse
import random
import traceback
import pickle

from bluezero import adapter
from bluezero.device import Device
from bluezero.central import Central

from utils.log_manager import LogManager
LogManager.init(level=logging.DEBUG)

from ble.advertiser import Advertiser
from ble.mobile_advertiser import MobileAdvertiser
from ble.carelink_advertiser import CareLinkAdvertiser
from ble.peripheral import PeripheralHandler, BleService, BleChar
from ble.sake import SakeHandler

import datetime as dt
import importlib
import sys

advertiser:Advertiser = None
sh:SakeHandler = None
device:Device = None
pump = None

# container for component instances
components = None

# Actions dict
actions = {}


class ReloadableComponents:
    def __init__(self, pump):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.pump = pump

        self.reinit()

    def reinit(self):
        def create(modulename, classname, arg):
            module = importlib.import_module(modulename)
            cls = getattr(module, classname)
            self.logger.info(f"Creating component {classname}")
            obj = cls(arg)
            self.__modules.append(modulename)
            self.__components.append(obj)
            return obj

        self.__components = []
        self.__modules    = []

        self.logger.info("Creating components ...")
        self.sgr         = create("cgm.reader",          "SGReader",              self.pump)
        self.socpc       = create("cgm.controller",      "SocpController",        self.pump)
        self.cgmm        = create("cgm.misc",            "CgmMiscData",           self.pump)
        self.certman     = create("services.cm",         "CertificateManagement", self.pump)
        self.hr          = create("history.reader",      "HistoryReader",         self.pump)
        self.hatss       = create("services.hats",       "HATS",                  self.pump)
        self.devinf      = create("device.info",         "DeviceInfo",            self.pump)
        self.iddstatus   = create("idd.status.reader",   "IDDStatusReader",       self.pump)
        self.iddfeatures = create("idd.features.reader", "IDDFeaturesReader",     self.pump)
        self.iddbattery  = create("idd.gst_battery",     "GSTBatteryLevel",       self.pump)
        # NOTE: uses history reader instead of pump
        self.dbm         = create("database.manager",    "DatabaseManager",       self.hr)

    def unsubscribe(self):
        self.logger.info("Unsubscribing components ...")
        for c in self.__components:
            c.unsubscribe()

    def reload_modules(self):
        self.logger.info("Reloading modules ...")
        for module_name in self.__modules:
            try:
                # remove module from sys.modules and reimport
                self.logger.debug(f"Reloading module {module_name}")
                if module_name in sys.modules:
                    del sys.modules[module_name]
                importlib.import_module(module_name)
            except Exception as e:
                self.logger.error(f"Reload failed for module {module_name}: {e}")


def reload_modules():
    global actions
    global components

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
    components.unsubscribe()

    # Clear actions dict first to break closures holding references
    actions.clear()

    # Remove modules from sys.modules and reimport
    components.reload_modules()

    # Reinitialize components and actions
    components.reinit()
    setup_actions()
    logging.info("Components re-initialized")
    return

def print_help():
    print("\n\n" + "="*40)
    print("Available commands:")
    for k, (desc, _) in actions.items():
        print(f"  {k}: {desc}")
    return

def setup_actions():
    global actions
    global components

    numbered_actions = [
        ('Read sensor glucose value', lambda: components.sgr.get_value()),
        ('Read sensor details',       lambda: components.socpc.read_sensor_details()),

        ('Read CGM run time',       lambda: components.cgmm.read_run_time()),
        ('Read CGM start time',     lambda: components.cgmm.read_start_time()),
        ('Read CGM remaining time', lambda: components.cgmm.calc_remaining_time()),
        ('Read CGM features',       lambda: components.cgmm.get_features()),

        ('Send certificate mgmt request', lambda: components.certman.send_request()),
        ('Send HATS request',             lambda: components.hatss.send_request()),

        ('Read IDD History - record count',    lambda: components.hr.get_available_record_count()),
        ('Read IDD History - last record',     lambda: components.hr.get_last_record()),
        ('Read IDD History - first record',    lambda: components.hr.get_first_record()),
        ('Read IDD History - last 10 records', lambda: components.hr.get_last_n_records()),

        ('Sync all history data to the database (may take several minutes!)', lambda: components.dbm.sync()),

        ('Read device info', lambda: components.devinf.get_device_info()),

        ('Read pump features', lambda: components.iddfeatures.get_pump_features()),

        ('Read IDD status - Get Time In Range',       lambda: components.iddstatus.get_time_in_range()),
        ('Read IDD status - Get Insulin On Board',    lambda: components.iddstatus.get_insulin_on_board()),
        ('Read IDD status - Get Therapy Algo States', lambda: components.iddstatus.get_therapy_algorithm_states()),
        ('Read IDD status - Get Active Basal Rate Delivery', lambda: components.iddstatus.get_active_basal_rate_delivery()),
        ('Read IDD status - Pump Status',             lambda: components.iddstatus.get_pump_status()),
        ('Read IDD GST Battery Level',                lambda: components.iddbattery.get_value()),

        ('IDD status test all calls', lambda: components.iddstatus.test_all()),
    ]

    actions = {
        'h': ('Show help/commands', lambda: print_help()),
        'r': ('Reload all modules', lambda: reload_modules()),
    }

    for i,act in enumerate(numbered_actions):
        actions[str(i + 1)] = act

def main_input_loop():

    while True:
        print("\n> ", end='')
        try:
            key = input().strip().lower()
        except UnicodeDecodeError:
            print("could not decode command!")
            continue

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
    global pump
    global components

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

            components = ReloadableComponents(pump)
            setup_actions()

            # Run main input loop
            print_help()
            main_input_loop()

def main():

    global ph
    global advertiser
    global sh
    global device

    # Fix bluezero's log messages showing up twice
    #
    # Since we are using the root logger in our LogManager, everything we do
    # with it affects *all* loggers. And since propagation of log events to
    # the parent loggers is enabled by default, bluezero's log messages show
    # up in their logger as well as in ours.
    #
    # We could choose to disable propagation and just use their log output. Or
    # we could disable their handlers and have bluezero's log messages show up
    # in our logger only. The latter is what we are doing here.
    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith("bluezero."):
            logging.info(f"Removing handlers for logger {logger_name}")
            bluezero_logger = logging.getLogger(logger_name)
            for h in bluezero_logger.handlers:
                bluezero_logger.removeHandler(h)

    def confirmation_code(string):
        try:
            code = int(string)
        except ValueError:
            raise argparse.ArgumentTypeError("not an integer")
        if code < 0 or code > 999999:
            raise argparse.ArgumentTypeError("not in range 000000..999999")
        return code

    # parse CLI args
    parser = argparse.ArgumentParser(description="Python Pump Connector")
    parser.add_argument('adv_name',
        nargs='?',
        help='Name to use for advertising. 0–7 ASCII characters. Will be chosen randomly if not supplied.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-r', '--reconnect',
        action='store_true',
        help='Reconnect to an already paired pump')
    group.add_argument('-c', '--carelink',
        metavar='CODE',
        type=confirmation_code,
        help='Connect to pump as CareLink device using the confirmation code CODE')
    parser.add_argument('-a', '--adapter-address',
        help='MAC address of the Bluetooth adapter to use')
    args = parser.parse_args()

    # check if bt is even on
    if not is_bluetooth_active():
       raise Exception("you need to have bluetooth running!")

    # The pump only reconnects to mobile devices that are using a Resolvable
    # Private Address (RPA). And it will only connect to CareLink devices that
    # do *not* use private addresses. Great.
    privacy_on = bt_privacy_on()
    if args.carelink is None:
        # mobile device
        if not privacy_on:
            raise Exception("BT privacy does not seem to be on. "
                + "Open /etc/bluetooth/main.conf and add 'Privacy = device' under [General]. "
                + "After that, restart the bluethoothd service and re-pair on your pump!")
    else:
        # CareLink device
        if privacy_on:
            raise Exception("BT privacy seems to be on. "
                + "Open /etc/bluetooth/main.conf and add 'Privacy = off' under [General]. "
                + "After that, restart the bluethoothd service and try again.")

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

    if args.reconnect:
        # NOTE: advertising name is ignored for reconnects
        adv_name = None
    else:
        forget_pump_devices()
        if args.adv_name is None:
            if args.carelink is None:
                # generate a random name for advertising as mobile device
                adv_name = str(random.randint(100000, 999999))
                logging.info(f"Generated random name for advertising: {adv_name}")
            else:
                # use default name for advertising as CareLink device
                adv_name = "PC"
        else:
            adv_name = args.adv_name

    if adv_name:
        logging.info(f"Creating advertiser with name '{adv_name}'")
    else:
        logging.info("Creating advertiser without name")

    if args.carelink is None:
        # advertise as mobile device (either for pairing or for reconnect)
        advertiser = MobileAdvertiser(adv_name, args.reconnect)
    else:
        # advertise as CareLink device
        advertiser = CareLinkAdvertiser(adv_name, adapter_addr, args.carelink)

    def on_connect(dev:Device):
        global device
        device = dev
        advertiser.on_connect_cb(dev)

    ph.set_on_connect(on_connect)
    ph.set_on_disconnect(advertiser.on_disconnect_cb)

    # device info service
    if args.carelink is None:
        # mobile devices define this with a custom service UUID
        dev_info_serv = BleService("00000900-0000-1000-0000-009132591325", "Device Info")
        ph.add_service(dev_info_serv)
        ph.add_char(dev_info_serv, BleChar("2A29", "Manufacturer Name",       "Google"))
        ph.add_char(dev_info_serv, BleChar("2A24", "Model Number",            "Nexus 5x"))
        ph.add_char(dev_info_serv, BleChar("2A25", "Serial Number",           "12345678"))
        ph.add_char(dev_info_serv, BleChar("2A27", "Hardware Revision",       "HW 1.0"))
        ph.add_char(dev_info_serv, BleChar("2A26", "Firmware Revision",       "FW 1.0"))
        ph.add_char(dev_info_serv, BleChar("2A28", "Software Revision",       "1.0.0"))
        ph.add_char(dev_info_serv, BleChar("2A23", "System ID",               bytes(8)))
        ph.add_char(dev_info_serv, BleChar("2A50", "PNP ID",                  bytes(7)))
        ph.add_char(dev_info_serv, BleChar("2A2A", "Certification Data List", bytes(0)))
    else:
        # CareLink devices define this with the standard service UUID
        #
        # NOTE: BlueZ started adding its own Device Info Service to the GATT
        #       table at some point. Defining our own service does not amend
        #       the existing one. Instead, there will be *two* services. And
        #       since both of them use the same UUID, this trips up the pump
        #       (and likely other devices).
        #
        #       In the Bluetooth config file, set `DeviceID = false` in the
        #       [General] section to deactivate BlueZ's default service. Note
        #       that this option did not properly work before BlueZ 5.57!
        dev_info_serv = BleService("180a", "Device Info")
        ph.add_service(dev_info_serv)
        ph.add_char(dev_info_serv, BleChar("2A29", "Manufacturer Name",       "Medtronic, Inc."))
        ph.add_char(dev_info_serv, BleChar("2A24", "Model Number",            "PC 1"))
        ph.add_char(dev_info_serv, BleChar("2A25", "Serial Number",           "PC3.13.0"))
        ph.add_char(dev_info_serv, BleChar("2A27", "Hardware Revision",       "1.0A"))
        ph.add_char(dev_info_serv, BleChar("2A26", "Firmware Revision",       "3.13.0"))
        ph.add_char(dev_info_serv, BleChar("2A28", "Software Revision",       "1.0S"))
        ph.add_char(dev_info_serv, BleChar("2A23", "System ID",               bytes.fromhex("00 23 F7 FF FE 00 40 49")))
        ph.add_char(dev_info_serv, BleChar("2A50", "PNP ID",                  bytes.fromhex("01 F9 01 30 35 33 37")))
        ph.add_char(dev_info_serv, BleChar("2A2A", "Certification Data List", bytes(0)))

    # SAKE service
    sake_serv = BleService("FE82", "Sake Service")
    sake_port = BleChar("0000FE82-0000-1000-0000-009132591325", "Sake Port", None, sh.notify_callback, sh.write_callback)
    ph.add_service(sake_serv)
    ph.add_char(sake_serv, sake_port)

    # finally before calling bluezero, start our advertisement and main logic thread
    advertiser.start_adv()

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

