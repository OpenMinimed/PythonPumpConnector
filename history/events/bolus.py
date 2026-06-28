from utils.base_enum import BaseEnum
from utils.parse_utils import ParseUtils

from history.enums import BolusType, BolusActivationType, BolusEndReason, BolusFlag
from history.events.base import HistoryEventData


class BolusProgrammedP1Data(HistoryEventData):
    """Event data for the Bolus Programmed Part 1 of 2 event"""
    def __init__(self, data: bytes):
        super().__init__(data)

        self.bolus_id: int | None = None
        self.bolus_type: int | None = None
        self.programmed_bolus_fast_amount: float | None = None
        self.programmed_bolus_extended_amount: float | None = None
        self.effective_bolus_duration: int | None = None

    def _parse_impl(self, data):
        self.bolus_id, data                         = ParseUtils.consume_u16(data)
        self.bolus_type, data                       = ParseUtils.consume_u8(data)
        self.programmed_bolus_fast_amount, data     = ParseUtils.consume_f32(data)
        self.programmed_bolus_extended_amount, data = ParseUtils.consume_f32(data)
        self.effective_bolus_duration, data         = ParseUtils.consume_u16(data)

        assert BolusType.contains_value(self.bolus_type)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Bolus ID:                         {self.bolus_id}",
            f"Bolus Type:                       {BolusType(self.bolus_type).name}",
            f"Programmed Bolus Fast Amount:     {self.programmed_bolus_fast_amount} IU",
            f"Programmed Bolus Extended Amount: {self.programmed_bolus_extended_amount} IU",
            f"Effective Bolus Duration:         {self.effective_bolus_duration} min",
        ]) + "\n)"


class BolusProgrammedP2Data(HistoryEventData):
    """Event data for the Bolus Programmed Part 2 of 2 event"""
    def __init__(self, data: bytes):
        super().__init__(data)

        self.flags: int | None = None
        self.bolus_delay_time: int | None = None
        self.bolus_template_number: int | None = None
        self.bolus_activation_type: int | None = None

    def _parse_impl(self, data):
        self.flags, data = ParseUtils.consume_u8(data)

        self.bolus_delay_time = None
        if self.flags & BolusFlag.BOLUS_DELAY_TIME_PRESENT:
            self.bolus_delay_time, data = ParseUtils.consume_u16(data)

        self.bolus_template_number = None
        if self.flags & BolusFlag.BOLUS_TEMPLATE_NUMBER_PRESENT:
            self.bolus_template_number, data = ParseUtils.consume_u8(data)

        self.bolus_activation_type = None
        if self.flags & BolusFlag.BOLUS_ACTIVATION_TYPE_PRESENT:
            self.bolus_activation_type, data = ParseUtils.consume_u8(data)
            assert BolusActivationType.contains_value(self.bolus_activation_type)

        return True, data

    def __str__(self):
        t = self.bolus_activation_type
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            "Flags:                 " + self._pp_flag_list(self.flags, BolusFlag),
            "Bolus Delay Time:      " + self._pp(self.bolus_delay_time),
            "Bolus Template Number: " + self._pp(self.bolus_template_number),
            "Bolus Activation Type: "
                + ("--" if t is None else BolusActivationType(t).name),
        ]) + "\n)"


class BolusDeliveredP1Data(HistoryEventData):
    """Event data for the Bolus Delivered Part 1 of 2 event"""
    def __init__(self, data: bytes):
        super().__init__(data)

        self.bolus_id: int | None = None
        self.bolus_type: int | None = None
        self.delivered_bolus_fast_amount: float | None = None
        self.delivered_bolus_extended_amount: float | None = None
        self.effective_bolus_duration: int | None = None

    def _parse_impl(self, data):
        self.bolus_id,                        data = ParseUtils.consume_u16(data)
        self.bolus_type,                      data = ParseUtils.consume_u8(data)
        self.delivered_bolus_fast_amount,     data = ParseUtils.consume_f32(data)
        self.delivered_bolus_extended_amount, data = ParseUtils.consume_f32(data)
        self.effective_bolus_duration,        data = ParseUtils.consume_u16(data)

        assert BolusType.contains_value(self.bolus_type)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Bolus ID:                        {self.bolus_id}",
            f"Bolus Type:                      {BolusType(self.bolus_type).name}",
            f"Delivered Bolus Fast Amount:     {self.delivered_bolus_fast_amount} IU",
            f"Delivered Bolus Extended Amount: {self.delivered_bolus_extended_amount} IU",
            f"Effective Bolus Duration:        {self.effective_bolus_duration} min",
        ]) + "\n)"


class BolusDeliveredP2Data(HistoryEventData):
    """Event data for the Bolus Delivered Part 2 of 2 event"""
    class Flag(BaseEnum):
        BOLUS_ACTIVATION_TYPE_PRESENT    = 1<<0
        BOLUS_END_REASON_PRESENT         = 1<<1
        ANNUNCIATION_INSTANCE_ID_PRESENT = 1<<2

    def __init__(self, data: bytes):
        super().__init__(data)

        self.flags: int | None = None
        self.bolus_start_time_offset: int | None = None
        self.bolus_activation_type: int | None = None
        self.bolus_end_reason: int | None = None
        self.annunciation_instance_id: int | None = None

    def _parse_impl(self, data):
        self.flags,                   data = ParseUtils.consume_u8(data)
        self.bolus_start_time_offset, data = ParseUtils.consume_u32(data)

        self.bolus_activation_type = None
        if self.flags & self.Flag.BOLUS_ACTIVATION_TYPE_PRESENT:
            self.bolus_activation_type, data = ParseUtils.consume_u8(data)
            assert BolusActivationType.contains_value(self.bolus_activation_type)

        self.bolus_end_reason = None
        if self.flags & self.Flag.BOLUS_END_REASON_PRESENT:
            self.bolus_end_reason, data = ParseUtils.consume_u8(data)
            assert BolusEndReason.contains_value(self.bolus_end_reason)

        self.annunciation_instance_id = None
        if self.flags & self.Flag.ANNUNCIATION_INSTANCE_ID_PRESENT:
            self.annunciation_instance_id, data = ParseUtils.consume_u16(data)

        return True, data

    def __str__(self):
        t = self.bolus_activation_type
        r = self.bolus_end_reason
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                    " + self._pp_flag_list(self.flags, self.Flag),
            f"Bolus Start Time Offset:  {self.bolus_start_time_offset} s",
            f"Bolus Activation Type:    "
                + ("--" if t is None else BolusActivationType(t).name),
            f"Bolus End Reason:         "
                + ("--" if r is None else BolusEndReason(r).name),
            f"Annunciation Instance ID: " + self._pp(self.annunciation_instance_id),
        ]) + "\n)"