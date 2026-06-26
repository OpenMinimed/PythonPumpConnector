import logging

from base_enum import BaseEnum
from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter

from socp_opcodes import SocpOpCode


class SensorDetailsFlags(BaseEnum):
    SENSOR_DETAILS_ANNUNCIATION_PRESENT  = 1<<0
    MAXIMUM_CALIBRATION_INTERVAL_PRESENT = 1<<1
    MAXIMUM_SENSOR_LIFE_PRESENT          = 1<<2
    SENSOR_FLEX_PACKAGE_VERSION_PRESENT  = 1<<3
    SENSOR_WARM_UP_PERIOD_PRESENT        = 1<<4


class SensorDetailsAnnunciation(BaseEnum):
    APPROVED_TREATMENT                 = 1<<0
    DISPOSABLE                         = 1<<1
    CAL_FREE                           = 1<<2
    HAS_CALIBRATION_RECOMMENDED        = 1<<3
    HAS_ABNORMAL_SG_INCREASE_DETECTION = 1<<4
    CALIBRATION_TRANSFER_SUPPORTED     = 1<<5


class SensorDetails:
    def __init__(self, data: bytes, use_e2e: bool = False):
        """
        :param data:    The raw data
        :param use_e2e: Whether to assume an E2E-CRC is included in the data
        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data
        self.use_e2e = use_e2e

        # parsed data
        self.flags: int | None = None
        self.annunciation: int | None = None
        self.maximum_calibration_interval: int | None = None
        self.maximum_sensor_life: int | None = None
        self.sensor_flex_package_version: int | None = None
        self.warmup_period: int | None = None

    def parse(self) -> bool:
        # minimal length is the size of the mandatory fields plus, optionally,
        # 2 bytes for the E2E-CRC
        min_length = 2
        if self.use_e2e:
            min_length += 2

        data = self.data
        length = len(data)

        if length < min_length:
            self.logger.error("Packet too short: wanted at least %d bytes, got %d"
                % (min_length, length))
            return False

        # validate E2E-CRC
        if self.use_e2e:
            if not ValueConverter.check_crc(data):
                self.logger.error("E2E-CRC mismatch")
                return False

            # snip CRC
            data = data[:-2]

        # mandatory fields
        opcode,     data = ParseUtils.consume_u8(data)
        self.flags, data = ParseUtils.consume_u8(data)

        expected_opcode = SocpOpCode.SENSOR_DETAILS_RESPONSE
        if opcode != expected_opcode:
            self.logger.error("Wrong response opcode: 0x%02x, wanted 0x%02x"
                % (opcode, expected_opcode))
            return False

        # Annunciation (optional)
        if self.flags & SensorDetailsFlags.SENSOR_DETAILS_ANNUNCIATION_PRESENT:
            self.annunciation, data = ParseUtils.consume_u16(data)

        # Maximum Calibration Interval (optional)
        if self.flags & SensorDetailsFlags.MAXIMUM_CALIBRATION_INTERVAL_PRESENT:
            self.maximum_calibration_interval, data = ParseUtils.consume_u16(data)

        # Maximum Sensor Life (optional)
        if self.flags & SensorDetailsFlags.MAXIMUM_SENSOR_LIFE_PRESENT:
            self.maximum_sensor_life, data = ParseUtils.consume_u16(data)

        # Sensor Flex Package Version (optional)
        if self.flags & SensorDetailsFlags.SENSOR_FLEX_PACKAGE_VERSION_PRESENT:
            self.sensor_flex_package_version, data = ParseUtils.consume_u16(data)

        # Warm-Up Period (optional)
        if self.flags & SensorDetailsFlags.SENSOR_WARM_UP_PERIOD_PRESENT:
            self.warmup_period, data = ParseUtils.consume_u8(data)

        # we are done, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra data in packet: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self) -> str:
        flags = ParseUtils.parse_flags(self.flags, SensorDetailsFlags)
        flag_list = ", ".join([f.name for f in flags])

        annunciation = ParseUtils.parse_flags(self.annunciation, SensorDetailsAnnunciation)
        annunciation_list = ", ".join([f.name for f in annunciation])

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                        "
                + ("--" if (self.flags is None or not flag_list) else flag_list),
            f"Annunciation:                 "
                + ("--" if (self.annunciation is None or not annunciation_list) else annunciation_list),
            # TODO: add proper unit
            f"Maximum Calibration Interval: "
                + ("--" if self.maximum_calibration_interval is None else f"{self.maximum_calibration_interval}"),
            f"Maximum Sensor Life:          "
                + ("--" if self.maximum_sensor_life is None else f"{self.maximum_sensor_life} min"),
            # TODO: add proper unit
            f"Sensor Flex Package Version:  "
                + ("--" if self.sensor_flex_package_version is None else f"{self.sensor_flex_package_version}"),
            # TODO: add proper unit
            f"Warm-Up Period:               "
                + ("--" if self.warmup_period is None else f"{self.warmup_period}"),
        ]) + "\n)"


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    raw = bytes.fromhex("91071d00ffff60273420")
    data = SensorDetails(raw, use_e2e=True)
    if data.parse():
        print(data)
    else:
        print("Failed to parse Sensor Details")

