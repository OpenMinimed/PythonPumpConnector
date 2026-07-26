from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from utils.gatt import GATTBase
from utils.log_manager import LogManager
from utils.uuids import UUID


class CertificateManagement(GATTBase):
    """
    Certificate Management
    """

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.cm_cp   = None
        self.cm_data = None

        success = self._configure_characteristics()
        assert success == True

    def unsubscribe(self):
        self.cm_data.add_characteristic_cb(None)
        self.cm_cp.add_characteristic_cb(None)
        return

    def send_request(self):
        ## Certificate Management Control Point char

        # Opcode: 0x00 (Get Certificate)
        #self.cm_cp.write_value([0x00])

        # CertificateManagementOpCode
        # GET_CERTIFICATE(0),
        # GET_ENROLLMENT(1),
        # SET_ENROLLMENT(2),
        # RESPONSE(3),
        # GET_CERTIFICATE_AUTHORITY(4),
        # SET_CERTIFICATE_AUTHORITY(5),
        # GET_REGISTRATION_AUTHORITY(6),
        # SET_REGISTRATION_AUTHORITY(7),
        # GET_FIRMWARE_AUTHORITY(8),
        # SET_FIRMWARE_AUTHORITY(9);
        self.cm_cp.write_value([9])

        
        return

    def _configure_characteristics(self):
        # CM service, Certificate Management Control Point characteristic
        self.cm_cp = self._add_char(UUID.CM_SERVICE, UUID.CM_CHAR_CP,
            ["write", "indicate"], callback=self._cmcp_cb)
        if self.cm_cp is None:
            return False

        # CM service, Certificate Managment Data characteristic
        self.cm_data = self._add_char(UUID.CM_SERVICE, UUID.CM_CHAR_DATA,
            ["write-without-response", "notify"], callback=self._data_cb)
        if self.cm_data is None:
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

