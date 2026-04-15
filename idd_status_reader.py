from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time
from enum import IntEnum

from log_manager import LogManager
from sake_handler import SakeHandler
from tir_data import TimeInRangeData
from uuids import UUID

class IddStatusReaderOpCode(IntEnum):
    RESPONSE_CODE = 771,
    RESET_STATUS = 780,
    GET_ACTIVE_BOLUS_IDS = 816,
    GET_ACTIVE_BOLUS_IDS_RESPONSE = 831,
    GET_ACTIVE_BOLUS_DELIVERY = 854,
    GET_ACTIVE_BOLUS_DELIVERY_RESPONSE = 857,
    GET_ACTIVE_BASAL_RATE_DELIVERY = 869,
    GET_ACTIVE_BASAL_RATE_DELIVERY_RESPONSE = 874,
    GET_INSULIN_ON_BOARD = 1011,
    GET_THERAPY_ALGORITHM_STATES = 1021,
    GET_THERAPY_ALGORITHM_STATES_RESPONSE = 1022,
    GET_INSULIN_ON_BOARD_RESPONSE = 1020,
    GET_DISPLAY_FORMAT = 1023,
    GET_DISPLAY_FORMAT_RESPONSE = 1024,
    GET_TIR_DATA = 1025,
    GET_TIR_DATA_RESPONSE = 1026,
    GET_SENSOR_WARM_UP_TIME_REMAINING = 1027,
    GET_SENSOR_WARM_UP_TIME_REMAINING_RESPONSE = 1028,
    GET_SENSOR_CALIBRATION_STATUS_ICON = 1029,
    GET_SENSOR_CALIBRATION_STATUS_ICON_RESPONSE = 1030,
    GET_EARLY_SENSOR_CALIBRATION_TIME = 1031,
    GET_EARLY_SENSOR_CALIBRATION_TIME_RESPONSE = 1032

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
        return

    def get_time_in_range(self):
        self.logger.info("Requesting Time In Range Data")
        opcode = IddStatusReaderOpCode.GET_TIR_DATA

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
        return

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
        return
