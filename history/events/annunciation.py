import datetime as dt

from utils.parse_utils import ParseUtils

from history.enums import AnnunciationEventFlag, AnnunciationType, PumpAnnunciationStatus
from history.events.base import HistoryEventData


class AnnunciationClearedData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.fault_id: int | None = None
        self.instance_id: int | None = None

    def _parse_impl(self, data):
        self.fault_type,  data = ParseUtils.consume_u16(data)
        self.instance_id, data = ParseUtils.consume_u16(data)

        return True, data

    def __str__(self):
        if AnnunciationType.contains_value(self.fault_type):
            t = AnnunciationType(self.fault_type).name
        else:
            t = f"unknown (0x{self.fault_type:04x})"

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Fault Type:  {t}",
            f"Instance ID: {self.instance_id}",
        ]) + "\n)"


class AnnunciationData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

        self.event_flags: int | None = None
        self.annunciation_id: int | None = None
        self.annunciation_type: int | None = None
        self.annunciation_status: PumpAnnunciationStatus | None = None
        self.timestamp: dt.datetime | None = None
        self.auxiliary_data: dict | None = None

    def _parse_impl(self, data):
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
            return True, data

        assert PumpAnnunciationStatus.contains_value(annunciation_status)
        self.annunciation_status = PumpAnnunciationStatus(annunciation_status)

        ref = dt.datetime(2000, 1, 1, 0, 0, 0, 0)
        self.timestamp = ref + dt.timedelta(seconds=timestamp)

        assert self.event_flags & AnnunciationEventFlag.AUXINFO1_PRESENT
        assert self.event_flags & AnnunciationEventFlag.AUXINFO2_PRESENT

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
            d["sg_value"], data = ParseUtils.consume_f16(data)
        elif self.annunciation_type in [
            AnnunciationType.LOW_RESERVOIR_ALERT,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            d["units_remaining"], data = ParseUtils.consume_f32(data)
        elif self.annunciation_type in [
            AnnunciationType.BOLUS_STOPPED,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO5_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO6_PRESENT
            d["units_programmed"], data = ParseUtils.consume_f32(data)
            d["units_delivered"],  data = ParseUtils.consume_f32(data)
        elif self.annunciation_type in [
            AnnunciationType.MAX_FIL_REACHED,
            AnnunciationType.MAX_FIL_REACHED_2,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
            assert self.event_flags & AnnunciationEventFlag.AUXINFO4_PRESENT
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
            _,                   data = ParseUtils.consume_u8(data)
        elif self.annunciation_type in [
            AnnunciationType.CL1_BOLUS_RECOMMENDED,
        ]:
            assert self.event_flags & AnnunciationEventFlag.AUXINFO3_PRESENT
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
            pass

        self.auxiliary_data = d

        return True, data

    def __str__(self):
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