from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from utils.gatt import GATTBase
from utils.log_manager import LogManager
from utils.uuids import UUID


class DeviceInfo(GATTBase):
    # 'SW' char does not seem to be used?

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central
        self._configure_characteristics()
        self._model: str = None
        self._serial: str = None
        self._hw: str = None
        self._fw: str = None
        return

    def unsubscribe(self):
        # no callbacks to remove
        return

    def read_battery_level(self) -> int:
        self.logger.debug("Fetching battery level from pump")
        raw = self.batt_char.read_raw_value()
        batt = int.from_bytes(dbus_tools.dbus_to_python(raw))
        return batt

    def get_device_info(self) -> str:
        batt = self.read_battery_level()
        toret = f"Pump {self.model}, SN: {self.serial}, HW: {self.hw}, FW: {self.fw}, BATT: {batt} % "
        self.logger.debug(toret)
        return toret

    @property
    def model(self):
        if self._model is None:
            self.logger.debug("Fetching model from pump")
            self._model = self._decode_string(self.model_char.read_raw_value())
        return self._model

    @property
    def serial(self):
        if self._serial is None:
            self.logger.debug("Fetching serial number from pump")
            self._serial = self._decode_string(self.serial_char.read_raw_value())
        return self._serial

    @property
    def hw(self):
        if self._hw is None:
            self.logger.debug("Fetching hardware version from pump")
            self._hw = self._decode_string(self.hw_char.read_raw_value())
        return self._hw

    @property
    def fw(self):
        if self._fw is None:
            self.logger.debug("Fetching firmware version from pump")
            self._fw = self._decode_string(self.fw_char.read_raw_value())
        return self._fw

    @staticmethod
    def _decode_string(raw):
        v = dbus_tools.dbus_to_python(raw)
        return v.split(b"\x00", 1)[0].decode()

    def _configure_characteristics(self):
        self.model_char = self._add_char(UUID.DIS_SERVICE, UUID.DIS_CHAR_MODEL_NO,
            ["read"])
        if self.model_char is None:
            return False

        self.serial_char = self._add_char(UUID.DIS_SERVICE, UUID.DIS_CHAR_SERIAL_NO,
            ["read"])
        if self.serial_char is None:
            return False

        self.hw_char = self._add_char(UUID.DIS_SERVICE, UUID.DIS_CHAR_HW_REV,
            ["read"])
        if self.hw_char is None:
            return False

        self.fw_char = self._add_char(UUID.DIS_SERVICE, UUID.DIS_CHAR_FW_REV,
            ["read"])
        if self.fw_char is None:
            return False

        self.batt_char = self._add_char(UUID.BATT_SERVICE, UUID.BATT_CHAR_LEVEL,
            ["read"])
        if self.batt_char is None:
            return False

        return True

