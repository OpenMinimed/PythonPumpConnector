from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from enum import IntEnum

from history_data import HistoryData
from log_manager import LogManager
from sake_handler import SakeHandler
from uuids import UUID


class IddRacpOpCode(IntEnum):
    REPORT_RECORDS = 51,
    DELETE_RECORDS = 60,
    ABORT_OPERATION = 85,
    REPORT_NUMBER_OF_RECORDS = 90,
    NUMBER_OF_RECORDS_RESPONSE = 102,
    RESPONSE_CODE = 15,

class IddRacpOperator(IntEnum):
    NULL = 15,
    ALL_RECORDS = 51,
    LESS_OR_EQUAL = 60,
    GREATER_OR_EQUAL = 85,
    WITHIN_RANGE = 90,
    FIRST_RECORD = 102,
    LAST_RECORD = 105,

class IddRacpFilterType(IntEnum):
    SEQUENCE_NUMBER = 15,
    SEQUENCE_NUMBER_REF_TIME_EVENTS = 51,
    SEQUENCE_NUMBER_NON_REF_TIME_EVENTS = 60,

class IddRacpResponseCode(IntEnum):
    SUCCESS = 240,
    OP_CODE_NOT_SUPPORTED = 2,
    INVALID_OPERATOR = 3,
    OPERATOR_NOT_SUPPORTED = 4,
    INVALID_OPERAND = 5,
    NO_RECORDS_FOUND = 6,
    ABORT_UNSUCCESSFUL = 7,
    PROCEDURE_NOT_COMPLETED = 8,
    OPERAND_NOT_SUPPORTED = 9,

class HistoryReader():
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

    see https://www.bluetooth.com/specifications/specs/html/?src=IDS_v1.0.2/out/en/index-en.html#UUID-4a0e985b-486b-5cdd-77d0-4dbc483cc322

    """

    EXPECTED_SUCC = bytes([IddRacpOpCode.RESPONSE_CODE, IddRacpOperator.NULL, IddRacpOpCode.REPORT_RECORDS, IddRacpResponseCode.SUCCESS])


    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.idd_history_data = None
        self.idd_racp         = None

        self.cp_finished = threading.Event()
        self.data_finished = threading.Event()

        self.records: list[bytearray] = []
        self.response = None
        self.sh = SakeHandler()
        self.timeout = 3 # default for single reads

        success = self._configure_characteristics()
        assert success == True
        return
    
    def __wait_for_cp_resp(self) -> None:
        if self.cp_finished.wait(timeout=self.timeout):
            self.logger.info("control point finished")
            return
        self.cp_finished = None
        raise RuntimeError("Timeout while waiting for control point to finish")
    
    def __wait_for_data_resp(self) -> None:
        """
        this might not be necessary, since the control point indication comes after all of the data has been transmitted. but i will keep it here, so we for sure wait for the first one at least.
        """

        if self.data_finished.wait(timeout=self.timeout):
            self.logger.info("data finished")
            return
        self.data_finished = None
        raise RuntimeError("Timeout while waiting for data to finish")
    
    def get_available_record_count(self) -> int:

        self.cp_finished = threading.Event()

        self.idd_racp.write_value([IddRacpOpCode.REPORT_NUMBER_OF_RECORDS, IddRacpOperator.ALL_RECORDS, IddRacpFilterType.SEQUENCE_NUMBER])

        self.__wait_for_cp_resp()

        # example: 66 0f d6 15 00 00
        expected = bytes([IddRacpOpCode.NUMBER_OF_RECORDS_RESPONSE, IddRacpFilterType.SEQUENCE_NUMBER])
        self.__check_expected(expected)
    
        count = int.from_bytes(self.response[2:4], byteorder="little")
        self.logger.debug(f"get_available_record_count = {count}")
        return count

    def __get_single_record(self, operator:IddRacpOperator) -> HistoryData:
        self.cp_finished = threading.Event()
    
        self.idd_racp.write_value([IddRacpOpCode.REPORT_RECORDS, operator, IddRacpFilterType.SEQUENCE_NUMBER])

        self.__wait_for_cp_resp()

        self.__check_expected(self.EXPECTED_SUCC)
    
        records = self.__parse_data()
        n = len(records)
        if n != 1:
            raise RuntimeError(f"Unexpected size of parsed records: {n}")
        
        return records[0]
    
    def __check_expected(self, expected: bytes):
        """
        only checks until the length of the input!
        """
        if self.response[:len(expected)] != expected:
            raise ValueError(
                f"Unexpected resp code {expected.hex() = } vs got {self.response.hex() = }"
            )
    
    def get_records_between(self, min:int, max:int) -> list[HistoryData]:
        
        # for me it goes with around 15 /s 
        exp_len = max - min
        timeout_bak = self.timeout
        self.timeout = ((1 / 15) *  exp_len) * 1.5 # overwrite timeout with a 50% tolerance
        self.logger.debug(f"setting timeout to {self.timeout}")

        self.cp_finished = threading.Event()
    
        self.logger.debug(f"reading record between {min} and {max}")
        packed_min = int.to_bytes(min + 1, length=4, byteorder="little") # + 1 to correct for inclusive comparison
        packed_max = int.to_bytes(max, length=4, byteorder="little")
        
        req = bytes([IddRacpOpCode.REPORT_RECORDS, IddRacpOperator.WITHIN_RANGE, IddRacpFilterType.SEQUENCE_NUMBER])
        req += packed_min
        req += packed_max
        self.logger.debug(f"sending request {req.hex()}")
        
        self.idd_racp.write_value(req)

        self.__wait_for_cp_resp()

        self.__check_expected(self.EXPECTED_SUCC)

        self.__wait_for_data_resp()

        toret = self.__parse_data()

        self.timeout = timeout_bak # TODO: this needs to be in the finally block of a try catch, else it stays like that during an exception
  
        if len(toret) != exp_len:
            raise RuntimeError(f"invalid count of data received: expected = {exp_len} vs actual: {len(toret)}")

        return toret
    
    def get_last_record(self) -> HistoryData:
        return self.__get_single_record(IddRacpOperator.LAST_RECORD)
    
    def get_first_record(self) -> HistoryData:
        return self.__get_single_record(IddRacpOperator.FIRST_RECORD)
    
    def get_last_n_records(self, n:int=10) -> list[HistoryData]:
        last = self.get_last_record()
        wanted = last.sequence_number - n
        return self.get_records_between(wanted, last.sequence_number)

    def __parse_data(self) -> list[HistoryData]:
        self.__wait_for_data_resp()
        self.logger.info(f"Received {len(self.records)} records")

        toret = []
        
        for raw_record in self.records:

            # TODO: For simplicity, we hard-code non-use of the E2E-Protection
            #       for now because the 780G never seems to have that enabled.
            #       The value should be read from th IDD Features
            #       characteristic instead.
            self.logger.info(f"raw history record: {raw_record.hex()}")
            history_record = HistoryData(raw_record, use_e2e=False)
            if history_record.parse():
                self.logger.debug(history_record)
                toret.append(history_record)
            else:
                self.logger.error("Failed to parse history record")
        self.records = []
        return toret
    
    def unsubscribe(self):
        self.idd_history_data.add_characteristic_cb(None)
        self.idd_racp.add_characteristic_cb(None)
        return

    def _configure_characteristics(self):

        try:
            # IDD service, IDD History Data characteristic
            self.logger.info("Adding characteristic IDD History Data")
            self.idd_history_data = self.central.add_characteristic(
                UUID.IDD_SERVICE, UUID.IDD_HISTORY_DATA_CHAR)
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
                UUID.IDD_SERVICE, UUID.IDD_RACP_CHAR)
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
            self.cp_finished.set()

    def _history_data_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = bytes(dbus_tools.dbus_to_python(changed_props["Value"]))
            self.logger.debug("IDD History Data notification: " + value.hex())
            data = self.sh.server.session.server_crypt.decrypt(value)
            self.records.append(data)
            self.data_finished.set()