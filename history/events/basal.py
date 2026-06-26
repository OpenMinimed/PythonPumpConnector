from utils.base_enum import BaseEnum
from utils.parse_utils import ParseUtils

from history.enums import BasalDeliveryContext, InsulinDeliveryStoppedReason, TBRType
from history.events.base import HistoryEventData


class DeliveredBasalRateChangedData(HistoryEventData):
    class Flag(BaseEnum):
        BASAL_DELIVERY_CONTEXT_PRESENT = 1<<0

    def __init__(self, data: bytes):
        super().__init__(data)

        self.flags: int | None = None
        self.old_basal_rate: float | None = None
        self.new_basal_rate: float | None = None
        self.basal_delivery_context: int | None = None

    def _parse_impl(self, data):
        self.flags,          data = ParseUtils.consume_u8(data)
        self.old_basal_rate, data = ParseUtils.consume_f32(data)
        self.new_basal_rate, data = ParseUtils.consume_f32(data)

        self.basal_delivery_context = None
        if self.flags & self.Flag.BASAL_DELIVERY_CONTEXT_PRESENT:
            self.basal_delivery_context, data = ParseUtils.consume_u8(data)
            assert BasalDeliveryContext.contains_value(self.basal_delivery_context)

        return True, data

    def __str__(self):
        c = self.basal_delivery_context
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                  " + self._pp_flag_list(self.flags, self.Flag),
            f"Old Basal Rate:         {self.old_basal_rate} IU/h",
            f"New Basal Rate:         {self.new_basal_rate} IU/h",
            f"Basal Delivery Context: "
                + ("--" if c is None else BasalDeliveryContext(c).name),
        ]) + "\n)"


class MaxBolusAmountChangedData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.old_amount: float | None = None
        self.new_amount: float | None = None

    def _parse_impl(self, data):
        self.old_amount, data = ParseUtils.consume_f32(data)
        self.new_amount, data = ParseUtils.consume_f32(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Old Amount: {self.old_amount} IU",
            f"New Amount: {self.new_amount} IU",
        ]) + "\n)"


class MicroBolusData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.bolus_number: int | None = None
        self.bolus_amount: float | None = None

    def _parse_impl(self, data):
        self.bolus_number, data = ParseUtils.consume_u8(data)
        self.bolus_amount, data = ParseUtils.consume_f32(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Bolus Number: {self.bolus_number}",
            f"Bolus Amount: {self.bolus_amount} IU",
        ]) + "\n)"


class MaxAutoBasalRateChangedData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.old_rate: float | None = None
        self.new_rate: float | None = None

    def _parse_impl(self, data):
        self.old_rate, data = ParseUtils.consume_f32(data)
        self.new_rate, data = ParseUtils.consume_f32(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Old Rate: {self.old_rate} IU/h",
            f"New Rate: {self.new_rate} IU/h",
        ]) + "\n)"


class TherapyContextData(HistoryEventData):
    class Flag(BaseEnum):
        SENSOR_ENABLED           = 1<<0
        BASAL_RATE_ACTIVE        = 1<<1
        AUTO_MODE_ACTIVE         = 1<<2
        INSULIN_DELIVERY_STOPPED = 1<<3
        TBR_ACTIVE               = 1<<4

    def __init__(self, data: bytes):
        super().__init__(data)

        self.flags: int | None = None
        self.basal_rate: float | None = None
        self.insulin_delivery_stopped_reason: int | None = None
        self.tbr_type: int | None = None
        self.tbr_adjustment: float | None = None

    def _parse_impl(self, data):
        self.flags, data = ParseUtils.consume_u8(data)

        self.basal_rate = None
        if self.flags & self.Flag.BASAL_RATE_ACTIVE:
            self.basal_rate, data = ParseUtils.consume_f32(data)

        self.insulin_delivery_stopped_reason = None
        if self.flags & self.Flag.INSULIN_DELIVERY_STOPPED:
            self.insulin_delivery_stopped_reason, data = ParseUtils.consume_u8(data)
            assert InsulinDeliveryStoppedReason.contains_value(self.insulin_delivery_stopped_reason)

        self.tbr_type       = None
        self.tbr_adjustment = None
        if self.flags & self.Flag.TBR_ACTIVE:
            self.tbr_type,       data = ParseUtils.consume_u8(data)
            self.tbr_adjustment, data = ParseUtils.consume_f32(data)
            assert TBRType.contains_value(self.tbr_type)

        return True, data

    def __str__(self):
        r = self.insulin_delivery_stopped_reason
        t = self.tbr_type
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                           " + self._pp_flag_list(self.flags, self.Flag),
            f"Basal Rate:                      " + self._pp(self.basal_rate, "IU/h"),
            f"Insulin Delivery Stopped Reason: "
                + ("--" if r is None else InsulinDeliveryStoppedReason(r).name),
            f"TBR Type:                        "
                + ("--" if t is None else TBRType(t).name),
            f"TBR Adjustment:                  " + self._pp(self.tbr_adjustment),
        ]) + "\n)"