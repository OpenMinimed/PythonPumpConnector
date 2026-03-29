import crc
import logging

from log_manager import LogManager


class HistoryData:
    """IDD History Data Record (Bluetooth LE)

    See https://www.bluetooth.com/specifications/specs/html/?src=IDS_v1.0.2/out/en/index-en.html#UUID-1871b14a-e54d-8364-bb22-76e5bedb1910
    for a definition of the record structure. Note that Medtronic adds
    the optional E2E-Counter field that the spec explicitly omits.

    """

    def __init__(self, data: bytes, use_e2e: bool = False):
        """
        :param data:    The raw record data
        :param use_e2e: Whether to assume E2E-Counter and E2E-CRC are included in the data

        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data
        self.use_e2e = use_e2e

        # parsed data
        self.event_type: int = None
        self.sequence_number: int = None
        self.relative_offset: int = None
        self.event_data: bytes = None

    def parse(self) -> bool:
        # minimal length is the size of the mandatory fields plus, optionally,
        # 3 bytes for the E2E-Counter and E2E-CRC
        min_length = 11 if self.use_e2e else 8

        data = self.data
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
            # extract and snip E2E-CRC from record (its last 2 bytes)
            crc = int.from_bytes(data[-2:], "little")
            data = data[:-2]

            # CRC of the remaining record
            computed_crc = self.e2e_crc(data)

            if crc != computed_crc:
                self.logger.error("E2E-CRC mismatch: computed %04x, got %04x"
                    % (computed_crc, crc))
                return False

            # snip E2E-Counter from record (we had to keep it until now
            # because it must be included in the CRC)
            data = data[:-1]

        # mandatory fields
        self.event_type,      data = self._consume(data, 2)
        self.sequence_number, data = self._consume(data, 4)
        self.relative_offset, data = self._consume(data, 2)
        self.event_data,      data = data, []
        # TODO: parse event data

        # we are done, there must not be any data left in the record
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Event Type:      0x{self.event_type:04x}",
            f"Sequence Number: {self.sequence_number}",
            f"Relative Offset: {self.relative_offset} s",
            f"Event Data:      {self.event_data.hex()}",
        ]) + "\n)"

    @staticmethod
    def _consume(data: bytes, n: int) -> int:
        # NOTE: copying this bytes object every time is rather wasteful
        assert n <= len(data)
        value = int.from_bytes(data[0:n], "little")
        return value, data[n:]

    @staticmethod
    def e2e_crc(data: bytes) -> int:
        calc = crc.Calculator(crc.Configuration(
            width=16,
            polynomial=0x1021,
            init_value=0xffff,
            final_xor_value=0,
            reverse_input=False,
            reverse_output=False,
        ))
        return calc.checksum(data)


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    #data = bytes.fromhex("660048e80000ea0406005a")
    data = bytes.fromhex("01f089d20000150b18404b4cf8")
    m = HistoryData(data)
    if m.parse():
        print(m)
    else:
        print("Failed to parse history data record")

