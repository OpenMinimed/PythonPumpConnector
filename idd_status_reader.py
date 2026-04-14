from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from log_manager import LogManager
from sake_handler import SakeHandler
from tir_data import TimeInRangeData
from uuids import UUID


class IDDStatusReader():
    def __init__(self, central: Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.idd_srcp = None

        self.sh = SakeHandler()
        self.operation_finished = threading.Event()
        self.response = None

        success = self._configure_characteristics()
        assert success == True

    def get_time_in_range(self):
        self.logger.info("Requesting Time In Range Data")
        opcode = 0x0401  # Get Time In Range Data

        # NOTE: We leave out E2E-Counter and E2E-CRC for now because the 780G
        #       never seems to have that enabled. The flag indicating whether
        #       to use E2E should be read from the IDD Features characteristic
        #       instead.
        request = int.to_bytes(opcode, length=2, byteorder="little")
        self.logger.debug(f"Sending request: {request.hex()}")

        # SAKE-encrypt and send
        ciph = self.sh.server.session.server_crypt.encrypt(request)
        self.idd_srcp.write_value(ciph)

        # wait for the response
        if self.operation_finished.wait(timeout=3):
            self.logger.info("Operation finished")
        else:
            self.logger.error("Timeout while waiting for operation to finish")
            return None

        # decrypt the response
        data = self.sh.server.session.server_crypt.decrypt(bytes(self.response))

        tir_data = TimeInRangeData(data)
        if tir_data.parse():
            self.logger.debug(tir_data)
        else:
            self.logger.error("Failed to parse Time In Range data")
            return None

        return tir_data

    def unsubscribe(self):
        self.idd_srcp.add_characteristic_cb(None)

    def _configure_characteristics(self):
        try:
            # IDD service, Status Reader Control Point characteristic
            self.logger.info("Adding characteristic SRCP")
            chrc = self.central.add_characteristic(
                UUID.IDD_SERVICE, UUID.IDD_SRCP_CHAR)
            while not chrc.resolve_gatt():
                time.sleep(0.2)
            assert "write"    in dbus_tools.dbus_to_python(chrc.flags)
            assert "indicate" in dbus_tools.dbus_to_python(chrc.flags)
            chrc.add_characteristic_cb(self._srcp_cb)
            chrc.start_notify()
            self.idd_srcp = chrc
        except Exception as e:
            self.logger.error("Failed to add characteristic SRCP")
            self.logger.error(e)
            return False

        return True

    def _srcp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("SRCP indication: " + value.hex())
            self.response = value
            self.operation_finished.set()

