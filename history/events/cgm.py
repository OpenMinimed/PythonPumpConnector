from utils.parse_utils import ParseUtils
from utils.value_converter import ValueConverter

from history.events.base import HistoryEventData


class SGMeasurementData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.time_offset: int | None = None
        self.sg_value: int | None = None
        self.isig: int | None = None
        self.v_counter: int | None = None

    def _parse_impl(self, data):
        self.time_offset, data = ParseUtils.consume_i16(data)
        self.sg_value,    data = ParseUtils.consume_u16(data)
        self.isig,        data = ParseUtils.consume_u16(data)
        self.v_counter,   data = ParseUtils.consume_i16(data)

        return True, data

    def __str__(self):
        sg = self.sg_value
        if sg == 0x0301:
            sg = "no value, sensor starting"
        elif sg == 0x0303:
            sg = "no value, sensor updating"
        elif sg == 0x0308:
            sg = "> 400 mg/dL"
        elif sg == 0x030d:
            sg = "< 50 mg/dL"
        else:
            sg = f"{sg} mg/dL"

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Time Offset: {self.time_offset} min",
            f"SG Value:    {sg}",
            f"ISIG:        {self.isig}",
            f"V Counter:   {self.v_counter}",
        ]) + "\n)"


class CGMAnalyticsData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.time_offset: int | None = None
        self.psgv: float | None = None
        self.cal_factor: int | None = None

    def _parse_impl(self, data):
        self.time_offset, data = ParseUtils.consume_i16(data)
        self.psgv,        data = ParseUtils.consume_f16(data)
        self.cal_factor,  data = ParseUtils.consume_u16(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Time Offset: {self.time_offset} min",
            f"PSGV:        {self.psgv}",
            f"Cal Factor:  {self.cal_factor}",
        ]) + "\n)"


class BgReadingData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.time_offset: int | None = None
        self.bg_value: float | None = None

    def _parse_impl(self, data):
        self.time_offset, data = ParseUtils.consume_i16(data)
        self.bg_value,    data = ParseUtils.consume_f16(data)

        return True, data

    def __str__(self):
        mgdl  = ValueConverter.kgl_to_mgdl(self.bg_value)
        mmolL = ValueConverter.mgdl_to_mmolL(mgdl)
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Time Offset: {self.time_offset} min",
            f"BG Value:    {self.bg_value} kg/L ({mgdl} mg/dL, {mmolL} mmol/L)",
        ]) + "\n)"


class CalibrationData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.time_offset: int | None = None
        self.bg_measurement: float | None = None

    def _parse_impl(self, data):
        self.time_offset,    data = ParseUtils.consume_i16(data)
        self.bg_measurement, data = ParseUtils.consume_f16(data)

        return True, data

    def __str__(self):
        mgdl  = ValueConverter.kgl_to_mgdl(self.bg_measurement)
        mmolL = ValueConverter.mgdl_to_mmolL(mgdl)
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Time Offset:    {self.time_offset} min",
            f"BG Measurement: {self.bg_measurement} kg/L ({mgdl} mg/dL, {mmolL} mmol/L)",
        ]) + "\n)"