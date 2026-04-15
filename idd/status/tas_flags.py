from enum import IntEnum

class TherapyAlgorithmStatesFlags(IntEnum):
    AUTO_MODE = 1,
    LGS_OPTION = 2,
    PLGM_OPTION = 4,
    TEMP_TARGET = 8,
    WAIT_TO_CALIBRATE = 16,
    SAFE_BASAL = 32,

class AutoModeReadinessState(IntEnum):
    NO_ACTION_REQUIRED = 0,
    BG_REQUIRED = 1,
    PROCESSING_BG = 2,
    WAIT_TO_ENTER_BG = 3,
    CALIBRATION_REQUIRED = 4,
    BG_RECOMMENDED = 5,

class AutoModeShieldState(IntEnum):
    OPEN_LOOP = 1,
    AUTO_BASAL_MODE = 2,
    SAFE_BASAL_MODE = 3,

class PlgmOrLgsState(IntEnum):
    FEATURE_ON_SG_UNAVAILABLE = 0,
    FEATURE_ON_SUSPENDED = 1,
    FEATURE_ON = 2,