from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from log_manager import LogManager
from sake_handler import SakeHandler
from uuids import UUID

from idd.features.pump_features import PumpFeatures


class IDDFeaturesReader():
    """Reads the IDD Features characteristic
    """

    def __init__(self, central: Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.idd_features = None

        self.sh = SakeHandler()

        success = self._configure_characteristics()
        assert success == True
        return

    def get_pump_features(self):
        self.logger.info("Reading IDD Features")

        raw = self.idd_features.read_raw_value()
        value = dbus_tools.dbus_to_python(raw)
        self.logger.debug("IDD Features: " + value.hex())

        # SAKE-decrypt the value
        data = self.sh.server.session.server_crypt.decrypt(value)

        pump_features = PumpFeatures(data)
        if pump_features.parse():
            self.logger.debug(pump_features)
        else:
            self.logger.error("Failed to parse pump features")
            return None

        return pump_features

    def unsubscribe(self):
        # no callbacks to remove
        return

    def _configure_characteristics(self):
        try:
            # IDD service, IDD Features characteristic
            self.logger.info("Adding characteristic IDD Features")
            chrc = self.central.add_characteristic(
                UUID.IDD_SERVICE, UUID.IDD_FEATURES_CHAR)
            while not chrc.resolve_gatt():
                time.sleep(0.2)
            assert "read" in dbus_tools.dbus_to_python(chrc.flags)
            self.idd_features = chrc
        except Exception as e:
            self.logger.error("Failed to add characteristic IDD Features")
            self.logger.error(e)
            return False

        return True

