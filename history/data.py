import crc
import logging
import datetime as dt

from utils.log_manager import LogManager
from utils.parse_utils import ParseUtils
from utils.value_converter import ValueConverter

from history.enums import HistoryEventType
from history.events import (
    BolusProgrammedP1Data,
    BolusProgrammedP2Data,
    BolusDeliveredP1Data,
    BolusDeliveredP2Data,
    DeliveredBasalRateChangedData,
    MaxBolusAmountChangedData,
    MicroBolusData,
    TherapyContextData,
    CL1TransitionData,
    MealData,
    BgReadingData,
    CalibrationData,
    InsulinDeliveryStoppedData,
    InsulinDeliveryRestartedData,
    SGMeasurementData,
    CGMAnalyticsData,
    NGPReferenceTimeData,
    AnnunciationClearedData,
    AnnunciationData,
    MaxAutoBasalRateChangedData,
    UnknownEventData,
)
from history.events.base import HistoryEventData


class HistoryData:
    """
    IDD History Data Record (Bluetooth LE)

    See https://www.bluetooth.com/specifications/specs/html/?src=IDS_v1.0.2/out/en/index-en.html#UUID-1871b14a-e54d-8364-bb22-76e5bedb1910
    for a definition of the record structure. Note that Medtronic adds
    the optional E2E-Counter field that the spec explicitly omits.

    """

    event_data_handlers = {
        #HistoryEventType.REFERENCE_TIME:
        HistoryEventType.BOLUS_PROGRAMMED_P1:          BolusProgrammedP1Data,
        HistoryEventType.BOLUS_PROGRAMMED_P2:          BolusProgrammedP2Data,
        HistoryEventType.BOLUS_DELIVERED_P1:           BolusDeliveredP1Data,
        HistoryEventType.BOLUS_DELIVERED_P2:           BolusDeliveredP2Data,
        HistoryEventType.DELIVERED_BASAL_RATE_CHANGED: DeliveredBasalRateChangedData,
        HistoryEventType.MAX_BOLUS_AMOUNT_CHANGED:     MaxBolusAmountChangedData,
        HistoryEventType.AUTO_BASAL_DELIVERY:          MicroBolusData,
        HistoryEventType.CL1_TRANSITION:               CL1TransitionData,
        HistoryEventType.THERAPY_CONTEXT:              TherapyContextData,
        HistoryEventType.MEAL:                         MealData,
        HistoryEventType.BG_READING:                   BgReadingData,
        HistoryEventType.CALIBRATION_COMPLETE:         CalibrationData,
        HistoryEventType.CALIBRATION_REJECTED:         CalibrationData,
        HistoryEventType.INSULIN_DELIVERY_STOPPED:     InsulinDeliveryStoppedData,
        HistoryEventType.INSULIN_DELIVERY_RESTARTED:   InsulinDeliveryRestartedData,
        HistoryEventType.SG_MEASUREMENT:               SGMeasurementData,
        HistoryEventType.CGM_ANALYTICS_DATA_BACKFILL:  CGMAnalyticsData,
        HistoryEventType.NGP_REFERENCE_TIME:           NGPReferenceTimeData,
        HistoryEventType.ANNUNCIATION_CLEARED:         AnnunciationClearedData,
        HistoryEventType.ANNUNCIATION_CONSOLIDATED:    AnnunciationData,
        HistoryEventType.MAX_AUTO_BASAL_RATE_CHANGED:  MaxAutoBasalRateChangedData,
    }

    def __init__(self, data: bytes, use_e2e: bool = False):
        """
        :param data:    The raw record data
        :param use_e2e: Whether to assume E2E-Counter and E2E-CRC are included in the data

        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.raw_data = data
        self.use_e2e = use_e2e

        self.event_type: HistoryEventType | None = None
        self.sequence_number: int | None = None
        self.relative_offset: int | None = None
        self.event_data: HistoryEventData | None = None

        self.abs_time: dt.datetime | None = None

    def parse(self, ref_time: dt.datetime | None = None) -> bool:
        # minimal length is the size of the mandatory fields plus, optionally,
        # 3 bytes for the E2E-Counter and E2E-CRC
        min_length = 11 if self.use_e2e else 8

        data = self.raw_data
        length = len(data)

        if length < min_length:
            self.logger.error("Record too short: wanted at least %d bytes, got %d"
                % (min_length, length))
            return False

        if self.use_e2e:

            # validate E2E-CRC
            #
            # TODO: Actually test this! This was not yet tested since the pump
            #       never uses E2E-Protection in this service.
            if not ValueConverter.check_crc(data):
                self.logger.error("E2E-CRC mismatch")
                return False

            # snip crc
            data = data[:-2]

            # snip E2E-Counter from record (we had to keep it until now
            # because it must be included in the CRC)
            data = data[:-1]

        # mandatory fields
        event_type_int,       data = ParseUtils.consume_u16(data)
        self.sequence_number, data = ParseUtils.consume_u32(data)
        self.relative_offset, data = ParseUtils.consume_u16(data)
        event_data_raw,       data = data, bytes([])

        # DEBUG: translate relative time to absolute time if a reference was
        #        provided
        if ref_time is not None:
            self.abs_time = ref_time + dt.timedelta(seconds=self.relative_offset)

        try:
            self.event_type = HistoryEventType(event_type_int)
        except ValueError:
            self.event_type = HistoryEventType.UNDEFINED

        # parse event data
        event_data = self.event_data_handlers.get(event_type_int, UnknownEventData)(event_data_raw)
        if not event_data.parse():
            self.logger.error(f"Failed to parse event data (type 0x{event_type_int:04x}): " + event_data_raw.hex())
            return False

        self.event_data = event_data

        # we are done, there must not be any data left in the record
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self):
        t = "" if self.abs_time is None else f" -> {self.abs_time}"

        event_data = str(self.event_data).splitlines()
        event_data = "\n    ".join(event_data)

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Event Type:      {self.event_type.name} (0x{self.event_type.value:04x})",
            f"Sequence Number: {self.sequence_number}",
            f"Relative Offset: {self.relative_offset} s{t}",
            f"Event Data:      {event_data}",
        ]) + "\n)"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("input",
        help="Text file with raw IDD History Data records as hexstrings")
    args = parser.parse_args()

    LogManager.init(level=logging.DEBUG)

    lines = []
    with open(args.input, "r") as f:
        lines = f.readlines()

    ref_time = None

    for i,s in enumerate(lines):
        data = bytes.fromhex(s.strip())
        history_data = HistoryData(data)
        if history_data.parse(ref_time):
            if history_data.event_type == HistoryEventType.NGP_REFERENCE_TIME:
                ref_time = history_data.event_data.date_time
            print(f"line {i}:", history_data)
        else:
            print(f"Failed to parse history data record in line {i+1}")
            exit(-1)