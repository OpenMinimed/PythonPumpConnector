import logging

from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter


class TimeInRangeData:
    """Time In Range Data (TIR)

    This record contains statistics about the SG values, specifically the
    fraction of time the value was within or ouside the defined target range.
    All values are given as percentages only.

    """

    def __init__(self, data: bytes, use_e2e: bool = False):
        """
        :param data:    The raw data
        :param use_e2e: Whether to assume E2E-Counter and E2E-CRC are included in the data
        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data
        self.use_e2e = use_e2e

        # parsed data
        self.not_enough_data: int | None = None
        self.above: int | None = None
        self.below: int | None = None
        self.in_range: int | None = None
        self.smart_guard: int | None = None

    def parse(self) -> bool:
        expected_length = 9 if self.use_e2e else 7

        data = self.data
        length = len(data)

        if length != expected_length:
            self.logger.error("Unexpected length: wanted %d bytes, got %d"
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

            # snip CRC
            data = data[:-2]

            # snip E2E-Counter (we had to keep it until now because it must be
            # included in the CRC)
            data = data[:-1]

        opcode,               data = ParseUtils.consume_u16(data)
        self.not_enough_data, data = ParseUtils.consume_u8(data)
        self.above,           data = ParseUtils.consume_u8(data)
        self.below,           data = ParseUtils.consume_u8(data)
        self.in_range,        data = ParseUtils.consume_u8(data)
        self.smart_guard,     data = ParseUtils.consume_u8(data)

        expected_opcode = 0x0402  # Get Time In Range Data Response
        if opcode != expected_opcode:
            self.logger.error("Wrong response opcode: 0x%04x, wanted 0x%04x"
                % (opcode, expected_opcode))
            return False

        # we are done, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Not Enough Data Flag: {self.not_enough_data}",
            f"Above:                {self.above:3d} %",
            f"Below:                {self.below:3d} %",
            f"In Range:             {self.in_range:3d} %",
            f"Smart Guard:          {self.smart_guard:3d} %",
        ]) + "\n)"


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    data = bytes.fromhex("0204001c024664")
    m = TimeInRangeData(data)
    if m.parse():
        print(m)
    else:
        print("Failed to parse Time In Range Data")

