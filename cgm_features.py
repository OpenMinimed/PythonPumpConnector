import logging

from base_enum import BaseEnum
from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter


class CGMFeatureFlags(BaseEnum):
    CALIBRATION                           = 1<<0
    PATIENT_HIGH_LOW_ALERTS               = 1<<1
    HYPO_ALERTS                           = 1<<2
    HYPER_ALERTS                          = 1<<3
    RATE_INCREASE_DECREASE_ALERTS         = 1<<4
    DEVICE_SPECIFIC_ALERT                 = 1<<5
    SENSOR_MALFUNCTION_DETECTION          = 1<<6
    SENSOR_TEMPERATURE_HIGH_LOW_DETECTION = 1<<7
    SENSOR_RESULT_HIGH_LOW_DETECTION      = 1<<8
    LOW_BATTERY_DETECTION                 = 1<<9
    SENSOR_TYPE_ERROR_DETECTION           = 1<<10
    GENERAL_DEVICE_FAULT                  = 1<<11
    E2E_CRC                               = 1<<12
    MULTIPLE_BOND                         = 1<<13
    MULTIPLE_SESSIONS                     = 1<<14
    CGM_TREND_INFORMATION                 = 1<<15
    CGM_QUALITY                           = 1<<16


class CGMType(BaseEnum):
    CAPILLARY_WHOLE_BLOOD    = 0x1
    CAPILLARY_PLASMA         = 0x2
    CAPILLARY_WHOLE_BLOOD_2  = 0x3
    VENOUS_PLASMA            = 0x4
    ARTERIAL_WHOLE_BLOOD     = 0x5
    ARTERIAL_PLASMA          = 0x6
    UNDETERMINED_WHOLE_BLOOD = 0x7
    UNDETERMINED_PLASMA      = 0x8
    INTERSTITIAL_FLUID       = 0x9
    CONTROL_SOLUTION         = 0xa


class CGMSampleLocation(BaseEnum):
    FINGER              = 0x1
    ALTERNATE_SITE_TEST = 0x2
    EARLOBE             = 0x3
    CONTROL_SOLUTION    = 0x4
    SUBCUTANEOUS_TISSUE = 0x5
    NOT_AVAILABLE       = 0xf


class CGMFeatures:
    """CGM Feature (Bluetooth LE)

    See https://www.bluetooth.com/de/specifications/gss/,
    section 3.42 CGM Feature for a definition of the structure.

    """

    def __init__(self, data: bytes):
        """
        :param data: The raw data
        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data

        # parsed data
        self.feature: int | None = None
        self.type: CGMType | None = None
        self.sample_location: CGMSampleLocation | None = None

    def parse(self) -> bool:
        expected_length = 6

        data = self.data
        length = len(data)

        if length != expected_length:
            self.logger.error("Unexpected length: wanted %d bytes, got %d"
                % (expected_length, length))
            return False

        # validate E2E-CRC
        # NOTE: Since the flag that indicates whether E2E-safety is supported
        #       or not is part of this very characteristic, the spec defines a
        #       workaround: The CRC field is always included in this packet. If
        #       E2E-safety is not supported, the CRC field is set to 0xffff.
        if data[:-2] != bytes([0xff,0xff]):
            if not ValueConverter.check_crc(data):
                self.logger.error("E2E-CRC mismatch")
                return False

            # snip CRC
            data = data[:-2]

        self.feature,         data = ParseUtils.consume(data, 3)
        type_sample_location, data = ParseUtils.consume_u8(data)

        cgm_type        =  type_sample_location       & 0xf
        sample_location = (type_sample_location >> 4) & 0xf

        assert CGMType.contains_value(cgm_type)
        self.type = CGMType(cgm_type)

        assert CGMSampleLocation.contains_value(sample_location)
        self.sample_location = CGMSampleLocation(sample_location)

        # we are done, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra data in packet: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self):
        flags = [""]
        for flag in CGMFeatureFlags:
            c = "X" if (self.feature & flag) else " " 
            flags.append(f"[{c}] {flag.name}")

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Feature:         "
                + ("--" if self.feature is None else f"\n{' '*8}".join(flags)),
            f"Type:            "
                + ("--" if self.type is None else self.type.name),
            f"Sample Location: "
                + ("--" if self.sample_location is None else self.sample_location.name),
        ]) + "\n)"


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    raw = bytes.fromhex("009001591404")
    data = CGMFeatures(raw)
    if data.parse():
        print(data)
    else:
        print("Failed to parse pump features")

