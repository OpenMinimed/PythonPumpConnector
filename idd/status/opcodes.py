from enum import IntEnum

class IddStatusReaderOpCode(IntEnum):
    RESPONSE_CODE                               = 0x0303
    RESET_STATUS                                = 0x030C
    GET_ACTIVE_BOLUS_IDS                        = 0x0330
    GET_ACTIVE_BOLUS_IDS_RESPONSE               = 0x033F
    GET_ACTIVE_BOLUS_DELIVERY                   = 0x0356
    GET_ACTIVE_BOLUS_DELIVERY_RESPONSE          = 0x0359
    GET_ACTIVE_BASAL_RATE_DELIVERY              = 0x0365
    GET_ACTIVE_BASAL_RATE_DELIVERY_RESPONSE     = 0x036A
    GET_TOTAL_DAILY_INSULIN_STATUS              = 0x0395
    GET_TOTAL_DAILY_INSULIN_STATUS_RESPONSE     = 0x039A
    GET_COUNTER                                 = 0x03A6
    GET_COUNTER_RESPONSE                        = 0x03A9
    GET_DELIVERED_INSULIN                       = 0x03C0
    GET_DELIVERED_INSULIN_RESPONSE              = 0x03CF
    GET_INSULIN_ON_BOARD                        = 0x03F3
    GET_INSULIN_ON_BOARD_RESPONSE               = 0x03FC
    # custom Medtronic opcodes:
    GET_THERAPY_ALGORITHM_STATES                = 0x03FD
    GET_THERAPY_ALGORITHM_STATES_RESPONSE       = 0x03FE
    GET_DISPLAY_FORMAT                          = 0x03FF
    GET_DISPLAY_FORMAT_RESPONSE                 = 0x0400
    GET_TIR_DATA                                = 0x0401  # TIR = Time in Range
    GET_TIR_DATA_RESPONSE                       = 0x0402
    GET_SENSOR_WARM_UP_TIME_REMAINING           = 0x0403
    GET_SENSOR_WARM_UP_TIME_REMAINING_RESPONSE  = 0x0404
    GET_SENSOR_CALIBRATION_STATUS_ICON          = 0x0405
    GET_SENSOR_CALIBRATION_STATUS_ICON_RESPONSE = 0x0406
    GET_EARLY_SENSOR_CALIBRATION_TIME           = 0x0407
    GET_EARLY_SENSOR_CALIBRATION_TIME_RESPONSE  = 0x0408

