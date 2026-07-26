from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from ble.sake import SakeHandler

from cgm.measurement import CGMMeasurement

from utils.gatt import GATTBase
from utils.log_manager import LogManager
from utils.uuids import UUID


class SGReader(GATTBase):

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

    def unsubscribe(self):
        self.cgm_measurement.add_characteristic_cb(None)
        self.cgm_racp.add_characteristic_cb(None)
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
        self.cgm_measurement = self._add_char(UUID.CGM_SERVICE, UUID.CGM_CHAR_MEASUREMENT,
            ["notify"], callback=self._measurement_cb)
        if self.cgm_measurement is None:
            return False

        # CGM service, Record Access Control Point characteristic
        self.cgm_racp = self._add_char(UUID.CGM_SERVICE, UUID.CGM_CHAR_RACP,
            ["write", "indicate"], callback=self._racp_cb)
        if self.cgm_racp is None:
            return False

        return True

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

