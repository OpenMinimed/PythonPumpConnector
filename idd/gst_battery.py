from bluezero import dbus_tools
from bluezero.central import Central

import time

from utils.log_manager import LogManager
from utils.uuids import UUID


class GSTBatteryLevel:
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
        try:
            # IDD service, GST Battery Level characteristic
            self.logger.info("Adding characteristic GST Battery Level")
            chrc = self.central.add_characteristic(
                UUID.IDD_SERVICE, UUID.IDD_GST_BATTERY_LEVEL_CHAR)
            while not chrc.resolve_gatt():
                time.sleep(0.2)
            assert "read" in dbus_tools.dbus_to_python(chrc.flags)
            chrc.start_notify()
            self.battery_level = chrc
        except Exception as e:
            self.logger.error("Failed to add characteristic GST Battery Level")
            self.logger.error(e)
            return False

        return True

