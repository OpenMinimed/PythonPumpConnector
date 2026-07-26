from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from utils.gatt import GATTBase
from utils.log_manager import LogManager
from utils.uuids import UUID


class DeviceInfo(GATTBase):

    model:str = None
    serial:str = None
    hw:str = None
    fw:str = None
    batt:int = None

    # 'SW' char does not seem to be used?

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central
        self._configure_characteristics()
        self.__trigger_read()
        self.read_battery_level()
        return

    def unsubscribe(self):
        # no callbacks to remove
        return

    def read_battery_level(self) -> int:
        raw = self.batt_char.read_raw_value()
        self.batt = int.from_bytes(dbus_tools.dbus_to_python(raw))
        return self.batt

    def get_device_info(self) -> str:
        self.read_battery_level()
        toret = f"Pump {self.model}, SN: {self.serial}, HW: {self.hw}, FW: {self.fw}, BATT: {self.batt} % "
        self.logger.debug(toret)
        return toret

    def __trigger_read(self):
        """
        Just read these once, during startup, since they should never change.
        """
        def decode_string(raw):
            v = dbus_tools.dbus_to_python(raw)
            return v.split(b"\x00", 1)[0].decode()

        self.logger.info("Trigger Device Info read...")
        self.model  = decode_string(self.model_char.read_raw_value())
        self.serial = decode_string(self.serial_char.read_raw_value())
        self.hw     = decode_string(self.hw_char.read_raw_value())
        self.fw     = decode_string(self.fw_char.read_raw_value())
        return 

    def _configure_characteristics(self):
        self.model_char = self._add_char(UUID.DIS_SERVICE, UUID.DIS_MODEL_NO_CHAR,
            ["read"])
        if self.model_char is None:
            return False

        self.serial_char = self._add_char(UUID.DIS_SERVICE, UUID.DIS_SERIAL_NO_CHAR,
            ["read"])
        if self.serial_char is None:
            return False

        self.hw_char = self._add_char(UUID.DIS_SERVICE, UUID.DIS_HW_REV_CHAR,
            ["read"])
        if self.hw_char is None:
            return False

        self.fw_char = self._add_char(UUID.DIS_SERVICE, UUID.DIS_FW_REV_CHAR,
            ["read"])
        if self.fw_char is None:
            return False

        self.batt_char = self._add_char(UUID.BATT_SERVICE, UUID.BATT_LEVEL_CHAR,
            ["read"])
        if self.batt_char is None:
            return False

        return True

