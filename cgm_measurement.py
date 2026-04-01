import logging

from log_manager import LogManager
from value_converter import ValueConverter


class CGMMeasurement:
    """CGM Measurement Record (Bluetooth LE)

    See https://www.bluetooth.com/de/specifications/gss/,
    section 3.43 CGM Measurement for a definition of the record
    structure.

    """

    def __init__(self, data: bytes, use_crc: bool = False):
        """
        :param data:    The raw record data
        :param use_crc: Whether to assume an E2E-CRC is included in the data

        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data
        self.use_crc = use_crc

        # parsed data
        self.flags: int = None
        self.glucose: float = None
        self.time_offset: int = None
        self.status: int = None
        self.cal_temp: int = None
        self.warning: int = None
        self.trend: float = None
        self.quality: float = None

    def parse(self) -> bool:
        # minimal length is the size of the mandatory fields plus, optionally,
        # 2 bytes for the E2E-CRC
        min_length = 8 if self.use_crc else 6

        data = self.data
        length = len(data)

        if length < min_length:
            self.logger.error("Record too short: wanted at least %d bytes, got %d"
                % (min_length, length))
            return False

        # validate E2E-CRC
        if self.use_crc:
            if not ValueConverter.check_crc(data):
                self.logger.error("E2E-CRC mismatch")
                return False
            data = data[:-2]


        # mandatory fields
        size,    data = self._consume(data, 1)
        flags,   data = self._consume(data, 1)
        glucose, data = self._consume(data, 2)
        offset,  data = self._consume(data, 2)

        if length != size:
            self.logger.error("Record length %d does not match size field %d"
                % (length, size))
            return False

        glucose = ValueConverter.decode_sfloat(glucose)

        # Sensor Status Annunciation (optional)

        status = 0
        if flags & 0x80:  # Status-Octet present
            status, data = self._consume(data, 1)

        cal_temp = 0
        if flags & 0x40:  # Cal/Temp-Octet present
            cal_temp, data = self._consume(data, 1)

        warning = 0
        if flags & 0x20:  # Warning-Octet present
            warning, data = self._consume(data, 1)

        # CGM Trend Information (optional)
        trend = None
        if flags & 0x01:  # CGM Trend Information present
            trend, data = self._consume(data, 2)
            trend = ValueConverter.decode_sfloat(trend)

        # CGM Quality (optional)
        quality = None
        if flags & 0x02:  # CGM Quality present
            quality, data = self._consume(data, 2)
            quality = ValueConverter.decode_sfloat(quality)

        # we are done, there must not be any data left in the record
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        self.flags       = flags
        self.glucose     = glucose
        self.time_offset = offset
        self.status      = status
        self.cal_temp    = cal_temp
        self.warning     = warning
        self.trend       = trend
        self.quality     = quality
        return True

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                     {self.flags:08b}",
            f"CGM Glucose Concentration: {self.glucose} mg/dL",
            f"Time Offset:               {self.time_offset} min",
            f"Status:                    {self.status:08b}",
            f"Cal/Temp:                  {self.cal_temp:08b}",
            f"Warning:                   {self.warning:08b}",
            f"CGM Trend Information:     "
                + ("--" if self.trend   is None else f"{self.trend} mg/dL/min"),
            f"CGM Quality:               "
                + ("--" if self.quality is None else f"{self.quality} %"),
        ]) + "\n)"

    @staticmethod
    def _consume(data: bytes, n: int) -> tuple[int, bytes]:
        # NOTE: copying this bytes object every time is rather wasteful
        assert n <= len(data)
        value = int.from_bytes(data[0:n], "little")
        return value, data[n:]


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    data = bytes.fromhex("0ec3f900f40b000074e00a00e0f1") # another for testing: 0ec38d00e803000010e00a00d9af
    m = CGMMeasurement(data, use_crc=True)
    if m.parse():
        print(m)
    else:
        print("Failed to parse measurement")
        