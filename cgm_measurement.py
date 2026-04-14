import logging

from log_manager import LogManager
from parse_utils import ParseUtils
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
        size,    data = ParseUtils.consume(data, 1)
        flags,   data = ParseUtils.consume(data, 1)
        glucose, data = ParseUtils.consume_f16(data)
        offset,  data = ParseUtils.consume(data, 2)

        if length != size:
            self.logger.error("Record length %d does not match size field %d"
                % (length, size))
            return False

        # Sensor Status Annunciation (optional)

        status = 0
        if flags & 0x80:  # Status-Octet present
            status, data = ParseUtils.consume(data, 1)

        cal_temp = 0
        if flags & 0x40:  # Cal/Temp-Octet present
            cal_temp, data = ParseUtils.consume(data, 1)

        warning = 0
        if flags & 0x20:  # Warning-Octet present
            warning, data = ParseUtils.consume(data, 1)

        # CGM Trend Information (optional)
        trend = None
        if flags & 0x01:  # CGM Trend Information present
            trend, data = ParseUtils.consume_f16(data)

        # CGM Quality (optional)
        quality = None
        if flags & 0x02:  # CGM Quality present
            quality, data = ParseUtils.consume_f16(data)

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
        self.quality     = quality # TODO: 100% is 10.0 ?? we need a bad quality signal to check this
        return True

    def __str__(self):
        trend_arrows = ""
        if self.trend is not None:
            # 780G's manual gives a relation between rise/fall rates and
            # arrows displayed:
            #
            # - 1 arrow: SG has been rising or falling at a rate of 20-40 mg/dL
            #   over the last 20 minutes, or 1-2 mg/dL per minute.
            #
            # - 2 arrows: SG has been rising or falling at a rate of 40-60 mg/dL
            #   over the last 20 minutes, or 2-3 mg/dL per minute.
            #
            # - 3 arrows: SG has been rising or falling at a rate of more than
            #   60 mg/dL over the last 20 minutes, or more than 3 mg/dL per
            #   minute.
            n = min(3, int(abs(self.trend)))
            if n > 0:
                arrow = "🠅" if self.trend > 0 else "🠇"
                trend_arrows = f" ({arrow*n})"

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                     {self.flags:08b}",
            f"CGM Glucose Concentration: {self.glucose} mg/dL ({ValueConverter.mgdl_to_mmolL(self.glucose)} mmol/L)",
            f"Time Offset:               {self.time_offset} min",
            f"Status:                    {self.status:08b}",
            f"Cal/Temp:                  {self.cal_temp:08b}",
            f"Warning:                   {self.warning:08b}",
            f"CGM Trend Information:     "
                + ("--" if self.trend   is None else f"{self.trend} mg/dL/min{trend_arrows}"),
            f"CGM Quality:               "
                + ("--" if self.quality is None else f"{self.quality} %"),
        ]) + "\n)"




if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    data = bytes.fromhex("0ec3f900f40b000074e00a00e0f1") # another for testing: 0ec38d00e803000010e00a00d9af
    m = CGMMeasurement(data, use_crc=True)
    if m.parse():
        print(m)
    else:
        print("Failed to parse measurement")
        