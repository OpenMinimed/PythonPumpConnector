from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from log_manager import LogManager

UUID_CM_SERVICE        = "00000600-0000-1000-0000-009132591325"
UUID_CM_CP_CHAR        = "00000601-0000-1000-0000-009132591325"
UUID_CM_DATA_CHAR      = "00000602-0000-1000-0000-009132591325"


class CertificateManagement:
    """Certificate Management

    """

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.cm_cp   = None
        self.cm_data = None

        success = self._configure_characteristics()
        assert success == True

    def send_request(self):
        ## Certificate Management Control Point char

        # Opcode: 0x00 (Get Certificate)
        #self.cm_cp.write_value([0x00])
        pass

    def _configure_characteristics(self):
        try:
            # CM service, Certificate Management Control Point characteristic
            self.logger.info("Adding characteristic CMCP")
            chrc = self.central.add_characteristic(
                UUID_CM_SERVICE, UUID_CM_CP_CHAR)
            while not chrc.resolve_gatt():
                time.sleep(0.2)
            assert "write"    in dbus_tools.dbus_to_python(chrc.flags)
            assert "indicate" in dbus_tools.dbus_to_python(chrc.flags)
            chrc.add_characteristic_cb(self._cmcp_cb)
            chrc.start_notify()
            self.cm_cp = chrc
        except Exception as e:
            self.logger.error("Failed to add characteristic CMCP")
            self.logger.error(e)
            return False

        try:
            # CM service, Certificate Managment Data characteristic
            self.logger.info("Adding characteristic Data")
            chrc = self.central.add_characteristic(
                UUID_CM_SERVICE, UUID_CM_DATA_CHAR)
            while not chrc.resolve_gatt():
                time.sleep(0.2)
            assert "write-without-response" in dbus_tools.dbus_to_python(chrc.flags)
            assert "notify"                 in dbus_tools.dbus_to_python(chrc.flags)
            chrc.add_characteristic_cb(self._data_cb)
            chrc.start_notify()
            self.cm_data = chrc
        except Exception as e:
            self.logger.error("Failed to add characteristic Data")
            self.logger.error(e)
            return False

        return True

    def _cmcp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("CMCP indication: " + value.hex())

    def _data_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("Data notification: " + value.hex())

