from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from log_manager import LogManager
from sake_handler import SakeHandler
from uuids import UUID

from idd.status.active_basal_rate_delivery import ActiveBasalRateDelivery
from idd.status.opcodes import IddStatusReaderOpCode
from idd.status.iob import InsulinOnBoardData
from idd.status.pump_status import PumpStatus
from idd.status.tas import TherapyAlgorithmStatesData
from idd.status.tir import TimeInRangeData

# see IddStatusReaderResponseConverter

class IDDStatusReader():

    def __init__(self, central: Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.idd_srcp = None
        self.idd_status = None

        self.sh = SakeHandler()
        self.operation_finished = threading.Event()
        self.response = None

        success = self._configure_characteristics()
        assert success == True
        return
    
    def test_all(self):
        funcs = [
            self.get_active_bolus_ids,
            self.get_time_in_range,
            # self.get_active_bolus_delivery, i get ATT error for this, probably it needs some argument
            self.get_active_basal_rate_delivery,
            self.get_insulin_on_board,
            self.get_therapy_algorithm_states,
            self.get_display_format,
            self.get_sensor_warm_up_time_remaining,
            self.get_sensor_calibration_status_icon,
            self.get_early_sensor_calibration_time,
            self.get_pump_status,
        ]
        for f in funcs:
            f()
            self.logger.debug("-"*20)

        return

    def get_time_in_range(self):
        self.logger.info("Requesting Time In Range Data")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_TIR_DATA)
        if data is None:
            return None

        tir_data = TimeInRangeData(data)
        if tir_data.parse():
            self.logger.debug(tir_data)
        else:
            self.logger.error("Failed to parse Time In Range data")
            return None

        return tir_data

    def get_active_bolus_ids(self):
        self.logger.info("Requesting Active Bolus IDs")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_ACTIVE_BOLUS_IDS)
        return data

    def get_active_bolus_delivery(self):
        self.logger.info("Requesting Active Bolus Delivery")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_ACTIVE_BOLUS_DELIVERY)
        return data

    def get_active_basal_rate_delivery(self):
        self.logger.info("Requesting Active Basal Rate Delivery")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_ACTIVE_BASAL_RATE_DELIVERY)
        if data is not None:
            obj = ActiveBasalRateDelivery(data)
            if obj.parse():
                self.logger.debug(obj)
                return obj
            else:
                self.logger.error("Failed to parse Active Basal Rate Delivery")
        return None

    def get_insulin_on_board(self) -> InsulinOnBoardData | None:
        self.logger.info("Requesting Insulin On Board")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_INSULIN_ON_BOARD)
        obj = InsulinOnBoardData(data)
        if obj.parse():
            self.logger.debug(obj)
            return obj
        return None

    def get_therapy_algorithm_states(self) -> TherapyAlgorithmStatesData | None:
        self.logger.info("Requesting Therapy Algorithm States")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_THERAPY_ALGORITHM_STATES)
        obj = TherapyAlgorithmStatesData(data)
        if obj.parse():
            self.logger.debug(obj)
            return obj
        return None

    def get_display_format(self):
        self.logger.info("Requesting Display Format")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_DISPLAY_FORMAT)
        return data

    def get_sensor_warm_up_time_remaining(self):
        # NOTE: Returns 'Response Code' with 'Op Code not supported' on the
        #       780G. Maybe only intended for direct communication with the
        #       sensor?
        self.logger.info("Requesting Sensor Warm Up Time Remaining")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_SENSOR_WARM_UP_TIME_REMAINING)
        return data

    def get_sensor_calibration_status_icon(self):
        # NOTE: Returns 'Response Code' with 'Op Code not supported' on the
        #       780G. Maybe only intended for direct communication with the
        #       sensor?
        self.logger.info("Requesting Sensor Calibration Status Icon")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_SENSOR_CALIBRATION_STATUS_ICON)
        return data

    def get_early_sensor_calibration_time(self):
        # NOTE: Returns 'Response Code' with 'Op Code not supported' on the
        #       780G. Maybe only intended for direct communication with the
        #       sensor?
        self.logger.info("Requesting Early Sensor Calibration Time")
        data = self._send_and_receive_opcode(IddStatusReaderOpCode.GET_EARLY_SENSOR_CALIBRATION_TIME)
        return data

    def get_pump_status(self):
        self.logger.info("Reading IDD Status")

        raw = self.idd_status.read_raw_value()
        value = dbus_tools.dbus_to_python(raw)
        self.logger.debug("IDD Status: " + value.hex())

        # SAKE-decrypt the value
        data = self.sh.server.session.server_crypt.decrypt(value)

        pump_status = PumpStatus(data)
        if pump_status.parse():
            self.logger.debug(pump_status)
        else:
            self.logger.error("Failed to parse pump status")
            return None

        return pump_status

    def unsubscribe(self):
        self.idd_srcp.add_characteristic_cb(None)
        return

    def _send_and_receive_opcode(self, opcode: IddStatusReaderOpCode):
        """
        Send an opcode request and wait for the response.
        
        Args:
            opcode: The opcode to send
            
        Returns:
            The decrypted response bytes, or None if an error occurred
        """
        # Clear the event before sending so we wait for the NEW response, not a stale one
        self.operation_finished.clear()
        
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
        data = self.sh.server.session.server_crypt.decrypt(self.response)
        self.response = None
        return data

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

        try:
            # IDD service, Status characteristic
            self.logger.info("Adding characteristic Status")
            chrc = self.central.add_characteristic(
                UUID.IDD_SERVICE, UUID.IDD_STATUS_CHAR)
            while not chrc.resolve_gatt():
                time.sleep(0.2)
            assert "read" in dbus_tools.dbus_to_python(chrc.flags)
            self.idd_status = chrc
        except Exception as e:
            self.logger.error("Failed to add characteristic Status")
            self.logger.error(e)
            return False

        return True

    def _srcp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("SRCP indication: " + value.hex())
            self.response = bytes(value)
            self.operation_finished.set()
        return
