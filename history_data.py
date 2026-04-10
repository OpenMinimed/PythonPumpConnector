import crc
import logging
import pickle

from enum import IntEnum

from log_manager import LogManager
from value_converter import ValueConverter

# Good resources: HistoryEventDataConvertersFactory

class HistoryEventType(IntEnum):
    UNDEFINED = 65535,
    REFERENCE_TIME = 15,
    BOLUS_PROGRAMMED_P1 = 90,
    BOLUS_PROGRAMMED_P2 = 102,
    BOLUS_DELIVERED_P1 = 105,
    BOLUS_DELIVERED_P2 = 150,
    AUTO_BASAL_DELIVERY_EVENT = 61441,
    DELIVERED_BASAL_RATE_CHANGED = 153,
    MEAL = 61445,
    THERAPY_CONTEXT_EVENT = 61444,
    BG_READING = 61447,
    CALIBRATION_COMPLETE = 61448,
    CALIBRATION_REJECTED = 61449,
    SG_MEASUREMENT = 61452,
    NGP_REFERENCE_TIME = 61454,
    CL1_TRANSITION_EVENT = 61442,
    INSULIN_DELIVERY_STOPPED_EVENT = 61450,
    INSULIN_DELIVERY_RESTARTED_EVENT = 61451,
    TEMP_BASAL_RATE_STARTED = 165,
    TEMP_BASAL_RATE_ENDED = 170,
    CGM_ANALYTICS_DATA_BACKFILL = 61453,
    ANNUNCIATION_CLEARED_EVENT = 61455,
    ANNUNCIATION_CONSOLIDATED_EVENT = 61456,
    MAX_BOLUS_AMOUNT_CHANGED = 1020,
    MAX_AUTO_BASAL_RATE_CHANGED = 61466,


class HistoryData:
    """
    IDD History Data Record (Bluetooth LE)

    See https://www.bluetooth.com/specifications/specs/html/?src=IDS_v1.0.2/out/en/index-en.html#UUID-1871b14a-e54d-8364-bb22-76e5bedb1910
    for a definition of the record structure. Note that Medtronic adds
    the optional E2E-Counter field that the spec explicitly omits.

    """

    def __init__(self, data: bytes, use_e2e: bool = False):
        """
        :param data:    The raw record data
        :param use_e2e: Whether to assume E2E-Counter and E2E-CRC are included in the data

        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data
        self.use_e2e = use_e2e

        # parsed data
        self.event_type: HistoryEventType = None
        self.sequence_number: int = None
        self.relative_offset: int = None
        self.event_data: bytes = None

    def parse(self) -> bool:
        # minimal length is the size of the mandatory fields plus, optionally,
        # 3 bytes for the E2E-Counter and E2E-CRC
        min_length = 11 if self.use_e2e else 8

        data = self.data
        length = len(data)

        if length < min_length:
            self.logger.error("Record too short: wanted at least %d bytes, got %d"
                % (min_length, length))
            return False

        # validate E2E-CRC
        #
        # TODO: Actually test this! This was not yet tested since the pump
        #       never uses E2E-Protection in this service.
        if self.use_e2e:

            if not ValueConverter.check_crc(data):
                self.logger.error("E2E-CRC mismatch")
                return False
            
            # snip crc
            data = data[:-2] 

            # snip E2E-Counter from record (we had to keep it until now
            # because it must be included in the CRC)
            data = data[:-1]

        # mandatory fields
        event_type_int, data = ValueConverter.consume(data, 2)
        try:
            self.event_type = HistoryEventType(event_type_int)
        except ValueError:
            self.event_type = HistoryEventType.UNDEFINED
        self.sequence_number, data = ValueConverter.consume(data, 4)
        self.relative_offset, data = ValueConverter.consume(data, 2)
        self.event_data,      data = data, []
        # TODO: parse event data

        # we are done, there must not be any data left in the record
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Event Type:      {self.event_type.name} (0x{self.event_type.value:04x})",
            f"Sequence Number: {self.sequence_number}",
            f"Relative Offset: {self.relative_offset} s",
            f"Event Data:      {self.event_data.hex()}",
        ]) + "\n)"



if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    parsed = [] # type: list[HistoryData]
    with open("history_data.pickle", "r") as f:
        lines = f.readlines()
        for l in lines:
            l = l.strip()
            d = bytes.fromhex(l)
            hd = pickle.loads(d)
            parsed.append(hd)

    types = []
    for record in parsed:
        print(record)
        if record.event_type.name not in types:
            types.append(record.event_type.name)
    
    print(f"parsed {len(parsed)} objects from dump file")
    print("types in the dump:")
    for t in types:
        print(f" {t}")