from utils.base_enum import BaseEnum


class HistoryEventType(BaseEnum):
    REFERENCE_TIME                   = 0x000f
    BOLUS_PROGRAMMED_P1              = 0x005a
    BOLUS_PROGRAMMED_P2              = 0x0066
    BOLUS_DELIVERED_P1               = 0x0069
    BOLUS_DELIVERED_P2               = 0x0096
    DELIVERED_BASAL_RATE_CHANGED     = 0x0099
    MAX_BOLUS_AMOUNT_CHANGED         = 0x03fc
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
    UNDEFINED                        = 0xffff


class BolusType(BaseEnum):
    UNDETERMINED = 0x0f
    FAST         = 0x33
    EXTENDED     = 0x3c
    MULTIWAVE    = 0xff


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


class BolusEndReason(BaseEnum):
    UNDETERMINED                = 0x0f
    PROGRAMMED_AMOUNT_DELIVERED = 0x33
    CANCELED                    = 0x3c
    ERROR_ABORT                 = 0x55


class BasalDeliveryContext(BaseEnum):
    UNDETERMINED                   = 0x0f
    DEVICE_BVASED                  = 0x33
    REMOTE_CONTROL                 = 0x3c
    ARTIFICIAL_PANCREAS_CONTROLLER = 0x55


class CL1TransitionState(BaseEnum):
    INTO_SI_PASS           = 0x00
    OUT_USER_OVERRIDE      = 0x01
    OUT_ALARM              = 0x02
    OUT_TIMEOUT_SAFE_BASAL = 0x03
    OUT_HIGH_SG            = 0x04


class InsulinDeliveryStoppedReason(BaseEnum):
    ALARM_SUSPENDED          = 0x01
    USER_SUSPENDED           = 0x02
    AUTO_SUSPENDED           = 0x03
    LOW_SG_SUSPENDED         = 0x04
    NOT_SEATED               = 0x05
    unknown_08               = 0x08
    PLGM_ON_LOW_SG_SUSPENDED = 0x0a


class TBRType(BaseEnum):
    UNDETERMINED = 0x0f
    ABSOLUTE     = 0x33
    RELATIVE     = 0x3c


class RecordingReason(BaseEnum):
    UNDETERMINED       = 0x0f
    SET_DATE_TIME      = 0x33
    PERIODIC_RECORDING = 0x3c
    DATE_TIME_LOSS     = 0x55


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
    INSERT_BATTERY_ALERT                  = 0x0054
    CHECK_BOLUS_BG_ALERT                  = 0x0067
    LOW_BATTERY_PUMP_ALERT                = 0x0068
    LOW_RESERVOIR_ALERT                   = 0x0069
    LOW_RESERVOIR_ALERT_2                 = 0x006a
    PERSONAL_REMINDER                     = 0x006c
    SET_CHANGE_REMINDERS                  = 0x006d
    IOB_CLEARED_ALERT                     = 0x0075
    CALIBRATE_NOW_ALERT                   = 0x0307
    CALIBRATION_NOT_ACCEPTED_ALERT        = 0x0308
    CHANGE_SENSOR_1                       = 0x0309
    CHANGE_SENSOR_2                       = 0x030a
    LOST_SENSOR_SIGNAL_ALERT              = 0x030c
    NO_SG_CALIBRATION_OCCURRED            = 0x0312
    CHANGE_SENSOR_3                       = 0x0315
    SENSOR_CONNECTED_ALERT                = 0x031e
    SENSOR_ERROR_ALERT                    = 0x0321
    LOW_SG_PLGM_ALERT                     = 0x0322
    LOW_SG_SUSPEND_ALERT                  = 0x0323
    ALERT_BEFORE_LOW_SG                   = 0x0325
    PREDICTIVE_RESUME_ALERT               = 0x0327
    THRESHOLD_SUSPEND_ALARM               = 0x0329
    LOW_SG_SUSPEND_BEFORE_LOW_QUITE_ALERT = 0x032a
    LOW_SG_SUSPEND_BEFORE_LOW_ALERT       = 0x032b
    LOW_SG_SUSPENSION_TIMEOUT             = 0x032e
    MANUAL_RESUME                         = 0x032f
    HIGH_SENSOR_GLUECOSE2                 = 0x0330
    HIGH_SG_ALERT                         = 0x0331
    CL1_EXIT_HIGH_SG                      = 0x0333
    CL1_EXIT_ALERT                        = 0x0334
    CL1_UMIN_ALERT                        = 0x0335
    CL1_UMAX_ALERT                        = 0x0336
    CL1_OFF_ALERT                         = 0x033a
    SEVERE_LOW_SG                         = 0x033b
    CL1_BOLUS_RECOMMENDED                 = 0x0341
    HIGH_SG_FOR_3_HOURS_ALERT             = 0x0344
    CALIBRATION_RECOMMENDED               = 0x0345
    FIRST_CALIBRATION_SUCCESSFUL          = 0x034b
    EARLY_CALIBRATION                     = 0x034c
    CALIBRATE_REMINDER                    = 0x0365


class PumpAnnunciationStatus(BaseEnum):
    UNDETERMINED = 0x0f
    PENDING      = 0x33
    SNOOZED      = 0x3c
    CONFIRMED    = 0x55


class InsulinDeliveryRestartedReason(BaseEnum):
    USER_SELECTS_RESUME                    = 0x01
    USER_CLEARS_ALARM                      = 0x02
    LGM_MANUAL_RESUME                      = 0x03
    LGM_AUTO_RESUME_DUE_MAX_SUSPENDED_TIME = 0x04
    LGM_AUTO_RESUME_DUE_PSG_AND_SG         = 0x05
    LGM_MANUAL_RESUME_VIA_DISABLE          = 0x06