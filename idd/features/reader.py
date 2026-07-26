from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from ble.sake import SakeHandler

from utils.gatt import GATTBase
from utils.log_manager import LogManager
from utils.uuids import UUID

from idd.features.pump_features import PumpFeatures


class IDDFeaturesReader(GATTBase):
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
        # IDD service, IDD Features characteristic
        self.idd_features = self._add_char(UUID.IDD_SERVICE, UUID.IDD_FEATURES_CHAR,
            ["read"])
        if self.idd_features is None:
            return False

        return True

