import logging

from base_enum import BaseEnum
from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter


class PumpFeatureFlags(BaseEnum):
    E2E_PROTECTION_SUPPORTED                        = 1<<0
    BASAL_RATE_SUPPORTED                            = 1<<1
    TBR_ABSOLUTE_SUPPORTED                          = 1<<2
    TBR_RELATIVE_SUPPORTED                          = 1<<3
    TBR_TEMPLATE_SUPPORTED                          = 1<<4
    FAST_BOLUS_SUPPORTED                            = 1<<5
    EXTENDED_BOLUS_SUPPORTED                        = 1<<6
    MULTIWAVE_BOLUS_SUPPORTED                       = 1<<7
    BOLUS_DELAY_TIME_SUPPORTED                      = 1<<8
    BOLUS_TEMPLATE_SUPPORTED                        = 1<<9
    BOLUS_ACTIVATION_TYPE_SUPPORTED                 = 1<<10
    MULTIPLE_BOND_SUPPORTED                         = 1<<11
    ISF_PROFILE_TEMPLATE_SUPPORTED                  = 1<<12
    I2CHO_PROFILE_TEMPLATE_SUPPORTED                = 1<<13
    TARGET_GLUCOSE_RANGE_PROFILE_TEMPLATE_SUPPORTED = 1<<14
    INSULIN_ON_BOARD_SUPPORTED                      = 1<<15
    FEATURE_EXTENSION                               = 1<<23
    RESERVOIR_SIZE_300IU_SUPPORTED                  = 1<<24
    GLUCOSE_UNIT_MG_DL_USED                         = 1<<25
    LGS_FEATURE_SUPPORTED                           = 1<<26
    PLGM_FEATURE_SUPPORTED                          = 1<<27
    HCL_FEATURE_SUPPORTED                           = 1<<28
    SMART_SETTINGS_SUPPORTED                        = 1<<29
    REMOTE_BOLUS_SUPPORTED                          = 1<<30
    FEATURE_EXTENSION_1                             = 1<<31
    EXTENDED_TIME_STAMP_SUPPORTED                   = 1<<32
    EXTENDED_TIME_OF_SENSOR_EXPIRATION_SUPPORTED    = 1<<33
    SENSOR_WARM_UP_TIME_REMAINING_SUPPORTED         = 1<<34
    SENSOR_CALIBRATION_STATUS_ICON_SUPPORTED        = 1<<35
    TWO_CALIBRATIONS_ONE_DAY_SUPPORTED              = 1<<36
    MATRIX_MENU_SUPPORTED                           = 1<<37


class PumpFeatures:
    def __init__(self, data: bytes):
        """
        :param data: The raw data
        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data

        # parsed data
        self.insulin_concentration: float | None = None
        self.flags: int | None = None

    def parse(self) -> bool:
        min_length = 8

        data = self.data
        length = len(data)

        if length < min_length:
            self.logger.error("Packet too short: wanted at least %d bytes, got %d"
                % (min_length, length))
            return False

        e2e_crc,                    data = ParseUtils.consume_u16(data)
        e2e_counter,                data = ParseUtils.consume_u8(data)
        self.insulin_concentration, data = ParseUtils.consume_f16(data)
        self.flags,                 data = ParseUtils.consume(data, 3)

        # validate E2E-CRC
        #
        # TODO: Implement this! If the bit E2E-Protection Supported in the
        #       Flags field is set, E2E-CRC and E2E-Counter are in use.
        #       Otherwise they are set to 0xffff and 0, respectively.
        #       For now, we assume the latter since the 780G never seems to
        #       use E2E-Protection in the Insulin Delivery Service.
        assert(e2e_crc == 0xffff)
        assert(e2e_counter == 0)

        shift = 24
        if self.flags & PumpFeatureFlags.FEATURE_EXTENSION:
            ext_flags, data = ParseUtils.consume_u8(data)
            self.flags |= (ext_flags << shift)

            # keep reading a byte if the respective Feature Extension bit (i.e.
            # the most significant bit) is set in the current flags byte
            while ext_flags & 0x80:
                shift += 8
                ext_flags, data = ParseUtils.consume_u8(data)
                self.flags |= (ext_flags << shift)

        # we are done, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra data in packet: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self):
        flags = [""]
        for flag in PumpFeatureFlags:
            if not flag.name.startswith("FEATURE_EXTENSION"):
                c = "X" if (self.flags & flag) else " " 
                flags.append(f"[{c}] {flag.name}")

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Insulin Concentration: "
                + ("--" if self.insulin_concentration is None else f"{self.insulin_concentration} IU/mL"),
            f"Flags:                 "
                + ("--" if self.flags is None else f"\n{' '*8}".join(flags)),
        ]) + "\n)"


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    raw = bytes.fromhex("ffff006400fede801f")
    data = PumpFeatures(raw)
    if data.parse():
        print(data)
    else:
        print("Failed to parse pump features")

