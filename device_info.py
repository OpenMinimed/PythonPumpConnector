from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from log_manager import LogManager
from uuids import UUID

class DeviceInfo():

    model:str = None
    serial:str = None
    hw:str = None
    fw:str = None
    batt:int = None

    # 'SW' char does not seem to be used?

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central
        self.fill_count = 0
        self.fill_order = ['model', 'serial', 'hw', 'fw'] # used by reflection, must match class attribute names!
        self._configure_characteristics()
        self.__trigger_read()
        self.read_battery_level()
        return
    
    def unsubscribe(self):
        for u in self.info_chars:
            u.add_characteristic_cb(None)
        self.batt_char.add_characteristic_cb(None)
        return
    
    # TODO: generalize all classes and maybe use this everywhere?
    def __add_char(self, service:UUID, char:UUID, expected_flags:str):
        toret = self.central.add_characteristic(service, char)
        while not toret.resolve_gatt():
            time.sleep(0.2)
        assert expected_flags in dbus_tools.dbus_to_python(toret.flags)
        return toret

    def read_battery_level(self) -> int:
        self.batt_event = threading.Event()
        self.batt_char.read_raw_value()
        self.batt_event.wait(timeout=1) # wait 1s for the new answer, else return the old 
        return self.batt
    
    def get_device_info(self) -> str:
        self.read_battery_level()
        toret = f"Pump {self.model}, SN: {self.serial}, HW:{self.hw}, FW: {self.fw}, BATT: {self.batt} % "
        self.logger.debug(toret)
        return toret

    def __trigger_read(self):
        """
        Just read these once, during startup, since they should never change.
        """
        self.logger.info("Trigger Device Info read...")
        for c in self.info_chars:
            c.read_raw_value()
        return 

    def _configure_characteristics(self):

        flags = "read"
        self.model_char = self.__add_char(UUID.DIS_SERVICE, UUID.DIS_MODEL_NO_CHAR, flags)
        self.serial_char = self.__add_char(UUID.DIS_SERVICE, UUID.DIS_SERIAL_NO_CHAR, flags)
        self.hw_char = self.__add_char(UUID.DIS_SERVICE, UUID.DIS_HW_REV_CHAR, flags)
        self.fw_char = self.__add_char(UUID.DIS_SERVICE, UUID.DIS_FW_REV_CHAR, flags)

        self.info_chars = [self.model_char, self.serial_char, self.hw_char, self.fw_char]

        for c in self.info_chars:
            c.add_characteristic_cb(self._generic_cb)

        self.batt_char = self.__add_char(UUID.BATT_SERVICE, UUID.BATT_LEVEL, flags)
        self.batt_char.add_characteristic_cb(self._batt_cb)
        
        return

    def _generic_cb(self, iface, changed_props, invalidated_props):

        if self.fill_count >= len(self.fill_order):
            self.logger.warning("unexpected device info callback, ignoring...")
            return
        
        if "Value" in changed_props:
            data = bytes(dbus_tools.dbus_to_python(changed_props["Value"]))
            self.logger.debug("device info callback: " + data.hex())
            data = data[:-1] # strip terminator
            decoded = data.decode()
            attr = self.fill_order[self.fill_count]
            setattr(self, attr, decoded)
            self.fill_count += 1
        return


    def _batt_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            data = bytes(dbus_tools.dbus_to_python(changed_props["Value"]))
            self.logger.debug("battery callback: " + data.hex())
            self.batt = data[0]
            if not (self.batt > 0 and self.batt < 101):
                raise RuntimeError(f"Invalid battery percentage received: {self.batt}")
            self.batt_event.set()
        return
