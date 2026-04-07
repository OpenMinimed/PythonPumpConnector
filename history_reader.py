from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from history_data import HistoryData
from log_manager import LogManager
from sake_handler import SakeHandler

UUID_IDD_SERVICE       = "00000100-0000-1000-0000-009132591325"
UUID_HISTORY_DATA_CHAR = "00000108-0000-1000-0000-009132591325"
UUID_RACP_CHAR         = "00002a52-0000-1000-8000-00805f9b34fb"


class HistoryReader:
    """
    Test for dumping event history through the pump's IDD service

    Records are requested on the Record Access Control Point (RACP).
    We then expect the pump to answer with one or multiple
    notifications on IDD History Data and to send a final response on
    the RACP which indicates whether the operation succeeded or not.

    Requesting a *number* of records works slightly different: We
    expect only the indication of RACP which includes the requested
    number, so IDD History Data is not involved in this case at all.

    The pump SAKE-encrypts the IDD History Data records. The RACP does
    not use any encryption though.

    """

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.idd_history_data = None
        self.idd_racp         = None

        self.operation_finished = threading.Event()
        self.records: list[bytearray] = []
        self.response = None
        self.sh = SakeHandler()

        success = self._configure_characteristics()
        assert success == True

    def get_records(self, timeout: int = 30):
        self.measurement_received = threading.Event()

        self.logger.info("Requesting record(s)")

        # IddRacpOperator
        
        # Op Code:  0x33 (Report Stored Records)
        # Op Code:  0x5a (Report Number of Stored Records)

        # Operator: 0x33 (All records)
        # Operator: 0x3c (Less than or equal to)
        # Operator: 0x5a (Within Range)
        # Operator: 0x66 (First Record)
        # Operator: 0x69 (Last Record)

        # Operand:  0x0f (Filter Type: Sequence Number)

        # get latest record
        self.idd_racp.write_value([0x33, 0x69, 0x0f])


        # NOTE: Careful with the following request! You may end up with being
        #       served thousands of records if you choose a bad filter
        #       parameter.
        #
        # Op Code:  0x33       (Report Stored Records)
        # Operator: 0x3c       (Less than or equal to)
        # Operand:  0x0f       (Filter Type: Sequence Number)
        # Operand:  0x000395f8 (Filter Parameter: maximum filter value)
        #self.idd_racp.write_value([0x33, 0x3c, 0x0f, 0xf8,0x95,0x03,0x00])


        # WARNING! THIS READS EVERYTHING! TAKES A FEW MINUTES!
        # self.idd_racp.write_value([0x33, 0x33, 0x0f])

        # TODO: how to handle timeout here? just ignore it maybe for now?
        # wait for a response
        if self.operation_finished.wait(timeout=timeout):
            self.logger.info("Operation finished")
        else:
            self.logger.error("Timeout while waiting for operation to finish")
            return None

        # parse received response
        #
        # see https://www.bluetooth.com/specifications/specs/html/?src=IDS_v1.0.2/out/en/index-en.html#UUID-4a0e985b-486b-5cdd-77d0-4dbc483cc322
        #
        # should be `0f0f33f0`:
        #   Op Code:               0x0f (Response Code)
        #   Operator:              0x0f (Null)
        #   Operand:
        #     Request Op Code:     0x33 (Report Stored Records)
        #     Response Code Value: 0xf0 (Success)
        if self.response[0] != 0x0f:
            self.logger.error("Unexpected op code: wanted Response Code (0x0f), got "
                + self.response[0].hex())
            return None
        if self.response != bytearray([0x0f, 0x0f, 0x33, 0xf0]):
            self.logger.error("Unexpected response")
            return None

        # process received records
        n = len(self.records)
        self.logger.info("Received %d record%s" % (n, "s" if n > 1 else ""))
        parsed_records = []
        for record in self.records:
            # decrypt the record
            data = self.sh.server.session.server_crypt.decrypt(bytes(record))

            # parse record
            #
            # TODO: For simplicity, we hard-code non-use of the E2E-Protection
            #       for now because the 780G never seems to have that enabled.
            #       The value should be read from th IDD Features
            #       characteristic instead.
            self.logger.info(f"raw history record: {data.hex()}")
            history_record = HistoryData(data, use_e2e=False)
            if history_record.parse():
                self.logger.debug(history_record)
                parsed_records.append(history_record)
            else:
                self.logger.error("Failed to parse history record")
                return None

        return parsed_records

    def _configure_characteristics(self):
        try:
            # IDD service, IDD History Data characteristic
            self.logger.info("Adding characteristic IDD History Data")
            self.idd_history_data = self.central.add_characteristic(
                UUID_IDD_SERVICE, UUID_HISTORY_DATA_CHAR)
            while not self.idd_history_data.resolve_gatt():
                time.sleep(0.2)
            assert "notify" in dbus_tools.dbus_to_python(self.idd_history_data.flags)
            self.idd_history_data.add_characteristic_cb(self._history_data_cb)
            self.idd_history_data.start_notify()
        except Exception as e:
            self.logger.error("Failed to add characteristic IDD History Data")
            self.logger.error(e)
            return False

        try:
            # IDD service, Record Access Control Point characteristic
            self.logger.info("Adding characteristic RACP")
            self.idd_racp = self.central.add_characteristic(
                UUID_IDD_SERVICE, UUID_RACP_CHAR)
            while not self.idd_racp.resolve_gatt():
                time.sleep(0.2)
            assert "write"    in dbus_tools.dbus_to_python(self.idd_racp.flags)
            assert "indicate" in dbus_tools.dbus_to_python(self.idd_racp.flags)
            self.idd_racp.add_characteristic_cb(self._racp_cb)
            self.idd_racp.start_notify()
        except Exception as e:
            self.logger.error("Failed to add characteristic RACP")
            self.logger.error(e)
            return False

        return True

    def _racp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("RACP indication: " + value.hex())
            self.response = value
            self.operation_finished.set()

    def _history_data_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("IDD History Data notification: " + value.hex())
            self.records.append(value)

