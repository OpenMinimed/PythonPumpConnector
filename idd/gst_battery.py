from bluezero import dbus_tools
from bluezero.central import Central

import time

from utils.gatt import GATTBase
from utils.log_manager import LogManager
from utils.uuids import UUID


class GSTBatteryLevel(GATTBase):
    """
    GST Battery Level (sensor's transmitter)
    """

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.battery_level = None

        success = self._configure_characteristics()
        assert success == True

    def unsubscribe(self):
        # no callbacks to remove
        return

    def get_value(self):
        self.logger.info("Reading GST Battery Level")

        raw = self.battery_level.read_raw_value()
        value = int.from_bytes(dbus_tools.dbus_to_python(raw))
        self.logger.debug(f"Battery Level: {value} %")

        return value

    def _configure_characteristics(self):
        # IDD service, GST Battery Level characteristic
        self.battery_level = self._add_char(UUID.IDD_SERVICE, UUID.IDD_CHAR_GST_BATTERY_LEVEL,
            ["read"])
        if self.battery_level is None:
            return False

        return True

