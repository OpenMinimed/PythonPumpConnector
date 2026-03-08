from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from log_manager import LogManager


UUID_CGM_SERVICE      = "0000181f-0000-1000-8000-00805f9b34fb"
UUID_MEASUREMENT_CHAR = "00002aa7-0000-1000-8000-00805f9b34fb"
UUID_RACP_CHAR        = "00002a52-0000-1000-8000-00805f9b34fb"


class SGReader:
    """Test for reading an SG value through the pump's CGM service

    The latest record is requested on the Record Access Control Point.
    We then expect the pump to answer with a CGM Measurement and to send
    a final response on the Record Access Control Point which indicates
    whether the operation succeeded or not.

    Note that is very hackish and is intended to do one very specific
    thing only. We may very much want to throw this away and completely
    rewrite the approach for use in some actual production code.
    """

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.cgm_measurement = None
        self.cgm_racp        = None

        self.measurement_received = threading.Event()
        self.operation_finished   = threading.Event()
        self.record   = None
        self.response = None

        success = self._configure_characteristics()
        assert success == True

    def get_value(self):
        self.measurement_received = threading.Event()

        self.logger.info("Requesting last stored record")

        # Op Code:  0x01 (Report Stored Records)
        # Operator: 0x06 (Last Record)
        self.cgm_racp.write_value([0x01, 0x06])

        # TODO: Fix this logic. We may only receive a (negative)
        #       response on RACP and no CGM measurement at all. Also,
        #       use some sane timeouts.
        if self.measurement_received.wait(timeout=None):
            self.logger.debug("Measurement received")
            self.operation_finished = threading.Event()
            if self.operation_finished.wait(timeout=None):
                self.logger.debug("Operation finished")
            else:
                self.logger.error("Timeout while waiting for operation to finish")
                return None
        else:
            self.logger.error("Timeout while waiting for measurement")
            return None

        # parse received record
        #
        # see https://www.bluetooth.com/de/specifications/gss/,
        # section 3.43 CGM Measurement
        length = len(self.record)
        if length < 6:
            self.logger.error("Record too short, wanted at least 6 bytes, got %d"
                % length)
            return None
        if length != self.record[0]:
            self.logger.error("Record length %d does not match length field %d"
                % (length, self.record[0]))
            return None
        flags         = self.record[1]
        concentration = self.as_f16(int.from_bytes(self.record[2:4], "little"))
        offset        = int.from_bytes(self.record[4:6], "little")
        print(f"Flags:                     {flags:08b}")
        print(f"CGM Glucose Concentration: {concentration} mg/dL")
        print(f"Time Offset:               {offset} min")

        # parse received response
        #
        # see https://www.bluetooth.com/de/specifications/gss/,
        # section 3.199 Record Access Control Point
        #
        # should be `06000101`:
        #   Op Code:               0x06 (Response Code)
        #   Operator:              0x00 (Null)
        #   Operand:
        #     Request Op Code:     0x01 (Report Stored Records)
        #     Response Code Value: 0x01 (Success)
        if self.response != bytearray([6,0,1,1]):
            self.logger.error("Unexpected response")

    @staticmethod
    def as_f16(value):
        e = (value & 0xf000) >> 12
        m = (value & 0x0fff)
        if e & 0x8:
            e = e - 0x10
        if m & 0x800:
            m = m - 0x1000
        return m * 10**e

    def _configure_characteristics(self):
        try:
            # CGM service, CGM Measurement characteristic
            self.logger.info("Adding characteristic CGM Measurement")
            self.cgm_measurement = self.central.add_characteristic(
                UUID_CGM_SERVICE, UUID_MEASUREMENT_CHAR)
            while not self.cgm_measurement.resolve_gatt():
                time.sleep(0.2)
            assert "notify" in dbus_tools.dbus_to_python(self.cgm_measurement.flags)
            self.cgm_measurement.add_characteristic_cb(self._measurement_cb)
            self.cgm_measurement.start_notify()
        except Exception as e:
            self.logger.error("Failed to add characteristic CGM Measurement")
            self.logger.error(e)
            return False

        try:
            # CGM service, Record Access Control Point characteristic
            self.logger.info("Adding characteristic RACP")
            self.cgm_racp = self.central.add_characteristic(
                UUID_CGM_SERVICE, UUID_RACP_CHAR)
            while not self.cgm_racp.resolve_gatt():
                time.sleep(0.2)
            assert "write"    in dbus_tools.dbus_to_python(self.cgm_racp.flags)
            assert "indicate" in dbus_tools.dbus_to_python(self.cgm_racp.flags)
            self.cgm_racp.add_characteristic_cb(self._racp_cb)
            self.cgm_racp.start_notify()
        except Exception as e:
            self.logger.error("Failed to add characteristic RACP")
            self.logger.error(e)
            return False

        return True

    def _racp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            self.logger.debug("CGM RACP indication: "
                + str(dbus_tools.dbus_to_python(changed_props)))
            self.response = dbus_tools.dbus_to_python(changed_props["Value"])
            self.operation_finished.set()

    def _measurement_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            self.logger.debug("CGM Measurement notification: "
                + str(dbus_tools.dbus_to_python(changed_props)))
            self.record = dbus_tools.dbus_to_python(changed_props["Value"])
            self.measurement_received.set()

