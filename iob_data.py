import logging

from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter


class InsulinOnBoardData:
    """Insulin On Board Data (IOB)

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
        self.flags: int | None = None
        self.insulin_on_board: float | None = None
        self.remaining_duration: int | None = None
        self.iob_partial_status_duration: int | None = None
        self.iob_partial_status_remaining: int | None = None

    def parse(self) -> bool:
        # minimal length is the size of the mandatory fields plus, optionally,
        # 3 bytes for the E2E-Counter and E2E-CRC
        min_length = 6 if self.use_e2e else 3

        data = self.data
        length = len(data)

        if length < min_length:
            self.logger.error("Packet too short: wanted at least %d bytes, got %d"
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

        # mandatory fields
        opcode,                data = ParseUtils.consume_u16(data)
        self.flags,            data = ParseUtils.consume_u8(data)
        self.insulin_on_board, data = ParseUtils.consume_f32(data)

        expected_opcode = 0x03fc  # Get Insulin On Board Response
        if opcode != expected_opcode:
            self.logger.error("Wrong response opcode: 0x%04x, wanted 0x%04x"
                % (opcode, expected_opcode))
            return False

        # Remaining Duration (optional)
        self.remaining_duration = None
        if self.flags & 0x01:  # Remaining Duration Present
            self.remaining_duration, data = ParseUtils.consume_u16(data)

        # IOB Partial Status (optional)
        self.iob_partial_status_duration = None
        self.iob_partial_status_remaining = None
        if self.flags & 0x02:  # IOB Partial Status Present
            self.iob_partial_status_duration,  data = ParseUtils.consume_u16(data)
            self.iob_partial_status_remaining, data = ParseUtils.consume_u16(data)

        # we are done, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self):
        flags = f"{self.flags:09_b}".replace("0", ".").replace("_", " ")
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                        {flags}",
            f"Insulin On Board:             {self.insulin_on_board} IU",
            f"Remaining Duration:           "
                + ("--" if self.remaining_duration is None else f"{self.remaining_duration} min"),
            f"IOB Partial Status Duration:  "
                + ("--" if self.iob_partial_status_duration is None else f"{self.iob_partial_status_duration} min"),
            # TODO: add unit
            f"IOB Partial Status Remaining: "
                + ("--" if self.iob_partial_status_remaining is None else f"{self.iob_partial_status_remaining}"),
        ]) + "\n)"


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    raw = bytes.fromhex("fc0300c05c15fa")
    data = InsulinOnBoardData(raw)
    if data.parse():
        print(data)
    else:
        print("Failed to parse Insulin On Board Data")

