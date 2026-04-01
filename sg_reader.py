from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from cgm_measurement import CGMMeasurement
from log_manager import LogManager

from sake_handler import SakeHandler

UUID_CGM_SERVICE      = "0000181f-0000-1000-8000-00805f9b34fb"
UUID_MEASUREMENT_CHAR = "00002aa7-0000-1000-8000-00805f9b34fb"
UUID_RACP_CHAR        = "00002a52-0000-1000-8000-00805f9b34fb"


class SGReader:

    """
    Test for reading an SG value through the pump's CGM service

    The latest record is requested on the Record Access Control Point.
    We then expect the pump to answer with a CGM Measurement and to send
    a final response on the Record Access Control Point which indicates
    whether the operation succeeded or not.

    The pump SAKE-encrypts the CGM Measurement data. The Record Access
    Control Point does not use any encryption though.

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
        self.record:bytearray   = None
        self.response = None

        self.sh = SakeHandler()

        self._configure_characteristics()
        return

    def get_value(self, timeout:int=3) -> float | None:
        self.measurement_received = threading.Event()

        self.logger.info("Requesting last stored record")

        # Op Code:  0x01 (Report Stored Records)
        # Operator: 0x06 (Last Record)
        self.cgm_racp.write_value([0x01, 0x06])
   
        # wait for a response
        if self.measurement_received.wait(timeout=timeout):
            self.logger.debug("Measurement received")

            if self.operation_finished.wait(timeout=timeout):
                self.logger.debug("Operation finished")
            else:
                self.logger.error("Timeout while waiting for operation to finish")
                return None
        else:
            self.logger.error("Timeout while waiting for measurement")
            return None

        # decrypt the record
        #self.logger.debug("Decrypting: " + bytes(self.record).hex() + " ...")
        data = self.sh.server.session.server_crypt.decrypt(bytes(self.record))
        #self.logger.debug("Decrypting: " + bytes(self.record).hex() + " ... DONE")

        # parse received record
        #
        # TODO: For simplicity, we hard-code use of the E2E-CRC for now
        #       because the 780G always seems to have that enabled. The value
        #       should be read from th CGM Feature characteristic instead.
        self.logger.debug(f"read raw cgm measurement = {data.hex()}")
        measurement_record = CGMMeasurement(data, use_crc=True)
        if measurement_record.parse():
            self.logger.debug(measurement_record)
        else:
            self.logger.error("Failed to parse measurement record")
            return None

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

        return float(measurement_record.glucose)


    def _configure_characteristics(self):

        # CGM service, CGM Measurement characteristic
        self.logger.info("Adding characteristic CGM Measurement")
        self.cgm_measurement = self.central.add_characteristic(
            UUID_CGM_SERVICE, UUID_MEASUREMENT_CHAR)
        while not self.cgm_measurement.resolve_gatt():
            time.sleep(0.2)
        assert "notify" in dbus_tools.dbus_to_python(self.cgm_measurement.flags)
        self.cgm_measurement.add_characteristic_cb(self._measurement_cb)
        self.logger.debug("measurement_cb added")
        self.cgm_measurement.start_notify()

        # CGM service, Record Access Control Point characteristic
        self.logger.info("Adding characteristic RACP")
        self.cgm_racp = self.central.add_characteristic(
            UUID_CGM_SERVICE, UUID_RACP_CHAR)
        while not self.cgm_racp.resolve_gatt():
            time.sleep(0.2)
        assert "write"    in dbus_tools.dbus_to_python(self.cgm_racp.flags)
        assert "indicate" in dbus_tools.dbus_to_python(self.cgm_racp.flags)
        self.cgm_racp.add_characteristic_cb(self._racp_cb)
        self.logger.debug("racp_cb added")
        self.cgm_racp.start_notify()
    
        return

    def _racp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            self.response = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("CGM RACP indication: " + self.response.hex())
            self.operation_finished.set()

    def _measurement_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            self.record = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("CGM Measurement notification: " + self.record.hex())
            self.measurement_received.set()

