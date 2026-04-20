import crc
import logging
import datetime as dt

from enum import IntEnum

from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter


class BaseEnum(IntEnum):
    @classmethod
    def contains_value(cls, v):
        return v in cls._value2member_map_


class HistoryEventType(BaseEnum):
    REFERENCE_TIME                   = 0x000f
    BOLUS_PROGRAMMED_P1              = 0x005a
    BOLUS_PROGRAMMED_P2              = 0x0066
    BOLUS_DELIVERED_P1               = 0x0069
    BOLUS_DELIVERED_P2               = 0x0096
    DELIVERED_BASAL_RATE_CHANGED     = 0x0099
    MAX_BOLUS_AMOUNT_CHANGED         = 0x03fc
    # custom Medtronic types:
    AUTO_BASAL_DELIVERY              = 0xf001
    CL1_TRANSITION                   = 0xf002
    THERAPY_CONTEXT                  = 0xf004
    MEAL                             = 0xf005
    BG_READING                       = 0xf007
    CALIBRATION_COMPLETE             = 0xf008
    CALIBRATION_REJECTED             = 0xf009
    INSULIN_DELIVERY_STOPPED         = 0xf00a
    INSULIN_DELIVERY_RESTARTED       = 0xf00b
    SG_MEASUREMENT                   = 0xf00c
    CGM_ANALYTICS_DATA_BACKFILL      = 0xf00d
    NGP_REFERENCE_TIME               = 0xf00e
    ANNUNCIATION_CLEARED             = 0xf00f
    ANNUNCIATION_CONSOLIDATED        = 0xf010
    MAX_AUTO_BASAL_RATE_CHANGED      = 0xf01a
    # our special catch-all type for event types not listed above:
    UNDEFINED                        = 0xffff


class HistoryEventData:
    def __init__(self, data: bytes):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self._raw = data

    def parse(self) -> bool:
        success, data = self._parse_impl(self._raw)
        if not success:
            return False

        # we are done parsing, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra event data after parsing: "
                + "%d byte(s) left, should be 0"  % len(data))
            return False

        return True

    def _parse_impl(self, data) -> tuple[bool, bytes]:
        # implementation goes only into the child classes
        return False, data

    @staticmethod
    def _pp(x, unit=""):
        if unit:
            unit = " " + unit
        return "--" if x is None else f"{x}{unit}"

    @staticmethod
    def _pp_flags(x):
        return f"{x:09_b}".replace("0", ".").replace("_", " ")

    @staticmethod
    def _pp_flag_list(x, flag_type):
        flags = ParseUtils.parse_flags(x, flag_type)
        return ", ".join([f.name for f in flags])


class UnknownEventData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

    def _parse_impl(self, data):
        return True, []

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"# TODO: implement handler for this event type",
            f"Data: {self._raw.hex()}",
        ]) + "\n)"


class BolusType(BaseEnum):
    UNDETERMINED = 0x0f
    FAST         = 0x33
    EXTENDED     = 0x3c
    MULTIWAVE    = 0xff


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
        # mandatory fields
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


class BolusActivationType(BaseEnum):
    UNDETERMINED                 = 0x0f
    MANUAL                       = 0x33
    RECOMMENDED                  = 0x3c
    MANUALLY_CHANGED_RECOMMENDED = 0x55
    COMMANDED                    = 0x5a


class BolusFlag(BaseEnum):
    BOLUS_DELAY_TIME_PRESENT         = 1<<0
    BOLUS_TEMPLATE_NUMBER_PRESENT    = 1<<1
    BOLUS_ACTIVATION_TYPE_PRESENT    = 1<<2
    BOLUS_DELIVERY_REASON_CORRECTION = 1<<3
    BOLUS_DELIVERY_REASON_MEAL       = 1<<4


class BolusProgrammedP2Data(HistoryEventData):
    """Event data for the Bolus Programmed Part 2 of 2 event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.flags: int | None = None
        self.bolus_delay_time: int | None = None
        self.bolus_template_number: int | None = None
        self.bolus_activation_type: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.flags, data = ParseUtils.consume_u8(data)

        # parse optional fields depending on flags

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
        # mandatory fields
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


class BolusEndReason(BaseEnum):
    UNDETERMINED                = 0x0f
    PROGRAMMED_AMOUNT_DELIVERED = 0x33
    CANCELED                    = 0x3c
    ERROR_ABORT                 = 0x55


class BolusDeliveredP2Data(HistoryEventData):
    """Event data for the Bolus Delivered Part 2 of 2 event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.flags: int | None = None
        self.bolus_start_time_offset: int | None = None
        self.bolus_activation_type: int | None = None
        self.bolus_end_reason: int | None = None
        self.annunciation_instance_id: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.flags,                   data = ParseUtils.consume_u8(data)
        self.bolus_start_time_offset, data = ParseUtils.consume_u32(data)

        # parse optional fields depending on flags

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

    class Flag(BaseEnum):
        BOLUS_ACTIVATION_TYPE_PRESENT    = 1<<0
        BOLUS_END_REASON_PRESENT         = 1<<1
        ANNUNCIATION_INSTANCE_ID_PRESENT = 1<<2

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


class BasalDeliveryContext(BaseEnum):
    UNDETERMINED                   = 0x0f
    DEVICE_BVASED                  = 0x33
    REMOTE_CONTROL                 = 0x3c
    ARTIFICIAL_PANCREAS_CONTROLLER = 0x55


class DeliveredBasalRateChangedData(HistoryEventData):
    """Event data for the Delivered Basal Rate Changed event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.flags: int | None = None
        self.old_basal_rate: float | None = None
        self.new_basal_rate: float | None = None
        self.basal_delivery_context: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.flags,          data = ParseUtils.consume_u8(data)
        self.old_basal_rate, data = ParseUtils.consume_f32(data)
        self.new_basal_rate, data = ParseUtils.consume_f32(data)

        # parse optional fields depending on flags

        self.basal_delivery_context = None
        if self.flags & self.Flag.BASAL_DELIVERY_CONTEXT_PRESENT:
            self.basal_delivery_context, data = ParseUtils.consume_u8(data)
            assert BasalDeliveryContext.contains_value(self.basal_delivery_context)

        return True, data

    class Flag(BaseEnum):
        BASAL_DELIVERY_CONTEXT_PRESENT = 1<<0

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
    """Event data for the Max Bolus Amount Changed Data event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.old_amount: float | None = None
        self.new_amount: float | None = None

    def _parse_impl(self, data):
        # mandatory fields
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
    """Event data for the Auto Basal Delivery event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.bolus_number: int | None = None
        self.bolus_amount: float | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.bolus_number, data = ParseUtils.consume_u8(data)
        self.bolus_amount, data = ParseUtils.consume_f32(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Bolus Number: {self.bolus_number}",
            f"Bolus Amount: {self.bolus_amount} IU",
        ]) + "\n)"


class CL1TransitionState(BaseEnum):
    INTO_SI_PASS           = 0x00
    OUT_USER_OVERRIDE      = 0x01
    OUT_ALARM              = 0x02
    OUT_TIMEOUT_SAFE_BASAL = 0x03
    OUT_HIGH_SG            = 0x04


class CL1TransitionData(HistoryEventData):
    """Event data for the CL1 Transition event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.transition_state: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.transition_state, data = ParseUtils.consume_u8(data)

        assert CL1TransitionState.contains_value(self.transition_state)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Transition State: {CL1TransitionState(self.transition_state).name}",
        ]) + "\n)"


class InsulinDeliveryStoppedReason(BaseEnum):
    ALARM_SUSPENDED          = 0x01
    USER_SUSPENDED           = 0x02
    AUTO_SUSPENDED           = 0x03
    LOW_SG_SUSPENDED         = 0x04
    NOT_SEATED               = 0x05
    PLGM_ON_LOW_SG_SUSPENDED = 0x0a


class TBRType(BaseEnum):
    UNDETERMINED = 0x0f
    ABSOLUTE     = 0x33
    RELATIVE     = 0x3c

class TherapyContextData(HistoryEventData):
    """Event data for the Therapy Context event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.flags: int | None = None
        self.basal_rate: float | None = None
        self.insulin_delivery_stopped_reason: int | None = None
        self.tbr_type: int | None = None
        self.tbr_adjustment: float | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.flags, data = ParseUtils.consume_u8(data)

        # parse optional fields depending on flags

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

    class Flag(BaseEnum):
        SENSOR_ENABLED           = 1<<0
        BASAL_RATE_ACTIVE        = 1<<1
        AUTO_MODE_ACTIVE         = 1<<2
        INSULIN_DELIVERY_STOPPED = 1<<3
        TBR_ACTIVE               = 1<<4

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


class MealData(HistoryEventData):
    """Event data for the Meal event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.food_amount: float | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.food_amount, data = ParseUtils.consume_f16(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Food Amount: {self.food_amount} g",
        ]) + "\n)"


class BgReadingData(HistoryEventData):
    """Event data for the BG Reading event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.time_offset: int | None = None
        self.bg_value: float | None = None

    def _parse_impl(self, data):
        # mandatory fields
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
    """Event data for the Calibration Complete and the Calibration Rejected events"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.time_offset: int | None = None
        self.bg_measurement: float | None = None

    def _parse_impl(self, data):
        # mandatory fields
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


class InsulinDeliveryStoppedData(HistoryEventData):
    """Event data for the Insulin Delivery Stopped event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.insulin_delivery_stopped_reason: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.insulin_delivery_stopped_reason, data = ParseUtils.consume_u8(data)

        assert InsulinDeliveryStoppedReason.contains_value(self.insulin_delivery_stopped_reason)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Insulin Delivery Stopped Reason: {InsulinDeliveryStoppedReason(self.insulin_delivery_stopped_reason).name}",
        ]) + "\n)"


class InsulinDeliveryRestartedReason(BaseEnum):
    USER_SELECTS_RESUME                    = 0x01
    USER_CLEARS_ALARM                      = 0x02
    LGM_MANUAL_RESUME                      = 0x03
    LGM_AUTO_RESUME_DUE_MAX_SUSPENDED_TIME = 0x04
    LGM_AUTO_RESUME_DUE_PSG_AND_SG         = 0x05
    LGM_MANUAL_RESUME_VIA_DISABLE          = 0x06


class InsulinDeliveryRestartedData(HistoryEventData):
    """Event data for the Insulin Delivery Restarted event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.insulin_delivery_restarted_reason: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.insulin_delivery_restarted_reason, data = ParseUtils.consume_u8(data)

        assert InsulinDeliveryRestartedReason.contains_value(self.insulin_delivery_restarted_reason)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Insulin Delivery Restarted Reason: {InsulinDeliveryRestartedReason(self.insulin_delivery_restarted_reason).name}",
        ]) + "\n)"


class SGMeasurementData(HistoryEventData):
    """Event data for the SG Measurement event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.time_offset: int | None = None
        self.sg_value: int | None = None
        self.isig: int | None = None
        self.v_counter: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.time_offset, data = ParseUtils.consume_i16(data)
        self.sg_value,    data = ParseUtils.consume_u16(data)
        self.isig,        data = ParseUtils.consume_u16(data)
        self.v_counter,   data = ParseUtils.consume_i16(data)

        return True, data

    def __str__(self):
        # handle special SG values
        sg = self.sg_value
        if sg == 0x0301:
            sg = "no value, sensor starting"
        elif sg == 0x0303:
            sg = "no value, sensor updating"
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
    """Event data for the CGM Analytics event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.time_offset: int | None = None
        self.psgv: float | None = None
        self.cal_factor: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
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


class RecordingReason(BaseEnum):
    UNDETERMINED       = 0x0f
    SET_DATE_TIME      = 0x33
    PERIODIC_RECORDING = 0x3c
    DATE_TIME_LOSS     = 0x55


class NGPReferenceTimeData(HistoryEventData):
    """Event data for the NGP Reference Time event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.recording_reason: int | None = None
        self.date_time: dt.datetime | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.recording_reason, data = ParseUtils.consume_u8(data)
        self.date_time,        data = ParseUtils.consume_datetime(data)

        assert RecordingReason.contains_value(self.recording_reason)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Recording Reason: {RecordingReason(self.recording_reason).name}",
            f"Date Time:        {self.date_time}",
        ]) + "\n)"


class AnnunciationEventFlag(BaseEnum):
    AUXINFO1_PRESENT = 1<<0
    AUXINFO2_PRESENT = 1<<1
    AUXINFO3_PRESENT = 1<<2
    AUXINFO4_PRESENT = 1<<3
    AUXINFO5_PRESENT = 1<<4
    AUXINFO6_PRESENT = 1<<5
    ALERT_SILENCED   = 1<<6


class AnnunciationType(BaseEnum):
    NO_DELIVERY                           = 0x0007
    FAULT8                                = 0x0008
    BOLUS_STOPPED                         = 0x0033
    MAX_FIL_REACHED                       = 0x0047
    MAX_FIL_REACHED_2                     = 0x0048
    CHECK_BOLUS_BG_ALERT                  = 0x0067
    LOW_RESERVOIR_ALERT                   = 0x0069
    LOW_RESERVOIR_ALERT_2                 = 0x006a
    PERSONAL_REMINDER                     = 0x006c
    SET_CHANGE_REMINDERS                  = 0x006d
    IOB_CLEARED_ALERT                     = 0x0075
    CALIBRATE_NOW_ALERT                   = 0x0307
    CHANGE_SENSOR_1                       = 0x0309
    CHANGE_SENSOR_2                       = 0x030a
    NO_SG_CALIBRATION_OCCURRED            = 0x0312
    CHANGE_SENSOR_3                       = 0x0315
    SENSOR_ERROR_ALERT                    = 0x0321
    LOW_SG_PLGM_ALERT                     = 0x0322
    LOW_SG_SUSPEND_ALERT                  = 0x0323
    PREDICTIVE_RESUME_ALERT               = 0x0327
    THRESHOLD_SUSPEND_ALARM               = 0x0329
    MANUAL_RESUME                         = 0x032f
    HIGH_SENSOR_GLUECOSE2                 = 0x0330
    CL1_EXIT_HIGH_SG                      = 0x0333
    CL1_EXIT_ALERT                        = 0x0334
    CL1_UMIN_ALERT                        = 0x0335
    CL1_UMAX_ALERT                        = 0x0336
    CL1_OFF_ALERT                         = 0x033a
    SEVERE_LOW_SG                         = 0x033b
    CL1_BOLUS_RECOMMENDED                 = 0x0341
    CALIBRATION_RECOMMENDED               = 0x0345
    FIRST_CALIBRATION_SUCCESSFUL          = 0x034b
    EARLY_CALIBRATION                     = 0x034c
    CALIBRATE_REMINDER                    = 0x0365


class PumpAnnunciationStatus(BaseEnum):
    UNDETERMINED = 0x0f
    PENDING      = 0x33
    SNOOZED      = 0x3c
    CONFIRMED    = 0x55


class AnnunciationClearedData(HistoryEventData):
    """Event data for the Annunciation Cleared event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.fault_id: int | None = None
        self.instance_id: int | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.fault_id,    data = ParseUtils.consume_u16(data)
        self.instance_id, data = ParseUtils.consume_u16(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Fault ID:    {self.fault_id}",
            f"Instance ID: {self.instance_id}",
        ]) + "\n)"


class AnnunciationData(HistoryEventData):
    """Event data for the Annunciation Consolidated event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.event_flags: int | None = None
        self.annunciation_id: int | None = None
        self.annunciation_type: int | None = None
        self.annunciation_status: AnnunciationStatus | None = None
        self.timestamp: dt.datetime | None = None
        self.auxiliary_data: dict | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.event_flags,     data = ParseUtils.consume_u8(data)
        self.annunciation_id, data = ParseUtils.consume_u16(data)
        annunciation_type,    data = ParseUtils.consume_u16(data)
        annunciation_status,  data = ParseUtils.consume_u8(data)
        timestamp,            data = ParseUtils.consume_u32(data)

        if annunciation_type & 0xf000 != 0xf000:
            self.logger.error(f"Unknown annunciation type: 0x{annunciation_type:04x}")
            return False, data

        self.annunciation_type = annunciation_type & 0x0fff
        if self.annunciation_type == 0:
            # TODO: assign a dummy AnnunciationType?
            return True, data

        # NOTE: There are so many possible annunciation types (potentially one
        #       for every alert the pump can display) that it seems better, for
        #       now, to just go with the raw number value here instead of
        #       converting to AnnunciationType and demanding that we have that
        #       particular value listed and named in there already.
        #assert AnnunciationType.contains_value(self.annunciation_type)
        #self.annunciation_type = AnnunciationType(self.annunciation_type)

        assert PumpAnnunciationStatus.contains_value(annunciation_status)
        self.annunciation_status = PumpAnnunciationStatus(annunciation_status)

        # seconds since 2000-01-01 00:00:00.000
        ref = dt.datetime(2000, 1, 1, 0, 0, 0, 0)
        self.timestamp = ref + dt.timedelta(seconds=timestamp)

        # NOTE: We ignore the AUXINFOx_PRESENT flags and just parse the
        #       auxiliary data by annunciation type, i.e. the number of
        #       expected bytes in that package depends on the type. It is not
        #       clear anyway why Medtronic shoehorned their data into the
        #       structure defined by the spec for the IDD Annunciation Status.
        #       They changed it already, by adding a 6th AuxInfo field and
        #       associated flag. Why not go fully custom then?
        #
        #       We just assert the presence of the appropriate AUXINFOx_PRESENT
        #       flags to have an additional sanity check.

        # The timestamp populates the first two AuxInfo fields. Since the
        # timestamp seems to be mandatory in Medtronic's annunciations, these
        # two flags should always be set.
        assert self.event_flags & AnnunciationEventFlag.AUXINFO1_PRESENT
        assert self.event_flags & AnnunciationEventFlag.AUXINFO2_PRESENT

        # Auxiliary Data (variable length and contents)
        d = {}
        if self.annunciation_type in [
            AnnunciationType.PREDICTIVE_RESUME_ALERT,
            AnnunciationType.NO_SG_CALIBRATION_OCCURRED,
            AnnunciationType.MANUAL_RESUME,
            AnnunciationType.CALIBRATE_REMINDER,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["contextual_time_minutes"], data = ParseUtils.consume_u8(data)
            d["contextual_time_hours"],   data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.LOW_SG_SUSPEND_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            # unit is mg/dL (?)
            d["sg_value"],                data = ParseUtils.consume_f16(data)
            d["contextual_time_minutes"], data = ParseUtils.consume_u8(data)
            d["contextual_time_hours"],   data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.LOW_SG_PLGM_ALERT,
            AnnunciationType.THRESHOLD_SUSPEND_ALARM,
            AnnunciationType.SEVERE_LOW_SG,
            AnnunciationType.HIGH_SENSOR_GLUECOSE2,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            # unit is mg/dL (?)
            d["sg_value"], data = ParseUtils.consume_f16(data)
        elif self.annunciation_type in [
            AnnunciationType.LOW_RESERVOIR_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            # unit is IU (?)
            d["units_remaining"], data = ParseUtils.consume_f32(data)
        elif self.annunciation_type in [
            AnnunciationType.BOLUS_STOPPED,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO5_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO6_PRESENT
            # unit is IU (?)
            d["units_programmed"], data = ParseUtils.consume_f32(data)
            # unit is IU (?)
            d["units_delivered"],  data = ParseUtils.consume_f32(data)
        elif self.annunciation_type in [
            AnnunciationType.MAX_FIL_REACHED,
            AnnunciationType.MAX_FIL_REACHED_2,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            # unit is IU (?)
            d["units_delivered"],  data = ParseUtils.consume_f32(data)
        elif self.annunciation_type in [
            AnnunciationType.CL1_EXIT_HIGH_SG,
            AnnunciationType.CL1_OFF_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["basal_pattern"], data = ParseUtils.consume_u8(data)
            _,                  data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.CL1_EXIT_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            d["basal_pattern"],      data = ParseUtils.consume_u8(data)
            _,                       data = ParseUtils.consume_u8(data)
            d["delivery_suspended"], data = ParseUtils.consume_u8(data)
            _,                       data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.CL1_UMIN_ALERT,
            AnnunciationType.CL1_UMAX_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["delivery_suspended"], data = ParseUtils.consume_u8(data)
            _,                       data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.CALIBRATION_RECOMMENDED,
            AnnunciationType.EARLY_CALIBRATION,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["sg_expiration_time_minutes"], data = ParseUtils.consume_u8(data)
            d["sg_expiration_time_hours"],   data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.FIRST_CALIBRATION_SUCCESSFUL,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO5_PRESENT
            d["early_calibration_time_minutes"],       data = ParseUtils.consume_u8(data)
            d["early_calibration_time_hours"],         data = ParseUtils.consume_u8(data)
            d["calibration_recommended_time_minutes"], data = ParseUtils.consume_u8(data)
            d["calibration_recommended_time_hours"],   data = ParseUtils.consume_u8(data)
            d["sg_expiration_time_minutes"],           data = ParseUtils.consume_u8(data)
            d["sg_expiration_time_hours"],             data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.NO_DELIVERY,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["occlusion_type"], data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.CL1_BOLUS_RECOMMENDED,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            # unit is kg/L
            d["bg_value"], data = ParseUtils.consume_f16(data)
        elif self.annunciation_type in [
             AnnunciationType.PERSONAL_REMINDER,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["reminder_name"], data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.SET_CHANGE_REMINDERS,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["days_since_set_change"], data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.CHECK_BOLUS_BG_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["duration_since_last_bolus"], data = ParseUtils.consume_u16(data)
        elif self.annunciation_type in [
            AnnunciationType.LOW_RESERVOIR_ALERT_2,
        ]:
            # NOTE: order of minutes and hours switched, compared to other
            #       annunciations
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["low_reservoir_time_remaining_hours"],   data = ParseUtils.consume_u8(data)
            d["low_reservoir_time_remaining_minutes"], data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.CALIBRATE_NOW_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["calibration_type"], data = ParseUtils.consume_u8(data)
            _,                     data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.CALIBRATE_NOW_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            d["wait_duration"], data = ParseUtils.consume_u8(data)
            _,                  data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.IOB_CLEARED_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            d["time_when_iob_cleared_minutes"],        data = ParseUtils.consume_u8(data)
            d["time_when_iob_cleared_hours"],          data = ParseUtils.consume_u8(data)
            d["iob_partial_status_remaining_minutes"], data = ParseUtils.consume_u8(data)
            d["iob_partial_status_remaining_hours"],   data = ParseUtils.consume_u8(data)
        else:
            # we assume that other annunciation types do not have any
            # auxiliary data
            pass

        self.auxiliary_data = d

        return True, data

    def __str__(self):
        # show annunciation type as name if we have it in our list
        if AnnunciationType.contains_value(self.annunciation_type):
            t = AnnunciationType(self.annunciation_type).name
        else:
            t = f"unknown (0x{self.annunciation_type:04x})"

        has_aux = ((self.auxiliary_data is not None)
            and (len(self.auxiliary_data) > 0))

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Event Flags:         " + self._pp_flag_list(self.event_flags, AnnunciationEventFlag),
            f"Annunciation ID:     {self.annunciation_id}",
            f"Annunciation Type:   " + t,
            f"Annunciation Status: " + self.annunciation_status.name,
            f"Timestamp:           {self.timestamp}",
            f"Auxiliary Data:      "
                + ("--" if not has_aux else str(self.auxiliary_data)),
        ]) + "\n)"


class MaxAutoBasalRateChangedData(HistoryEventData):
    """Event data for the Max Auto Basal Rate Changed event"""

    def __init__(self, data: bytes):
        super().__init__(data)

        self.old_rate: float | None = None
        self.new_rate: float | None = None

    def _parse_impl(self, data):
        # mandatory fields
        self.old_rate, data = ParseUtils.consume_f32(data)
        self.new_rate, data = ParseUtils.consume_f32(data)

        return True, data

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Old Rate: {self.old_rate} IU/h",
            f"New Rate: {self.new_rate} IU/h",
        ]) + "\n)"


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

        # parsed data
        self.event_type: HistoryEventType | None = None
        self.sequence_number: int | None = None
        self.relative_offset: int | None = None # in seconds
        self.event_data: HistoryEventData | None = None

        self.__abs_time: dt.datetime | None = None

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
        event_type_int,       data = ParseUtils.consume_u16(data)
        self.sequence_number, data = ParseUtils.consume_u32(data)
        self.relative_offset, data = ParseUtils.consume_u16(data)
        event_data_raw,       data = data, bytes([])

        # DEBUG: translate relative time to absolute time if a reference was
        #        provided
        if ref_time is not None:
            self.__abs_time = ref_time + dt.timedelta(seconds=self.relative_offset)

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
        t = "" if self.__abs_time is None else f" -> {self.__abs_time}"

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

