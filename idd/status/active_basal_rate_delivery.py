import logging

from base_enum import BaseEnum
from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter

from idd.status.opcodes import IddStatusReaderOpCode


class ActiveBasalRateFlags(BaseEnum):
    TBR_PRESENT                    = 1<<0
    TBR_TEMPLATE_NUMBER_PRESENT    = 1<<1
    BASAL_DELIVERY_CONTEXT_PRESENT = 1<<2


class TBRType(BaseEnum):
    UNDETERMINED = 0x0f
    ABSOLUTE     = 0x33
    RELATIVE     = 0x3c


class BasalDeliveryContext(BaseEnum):
    UNDETERMINED   = 0x0f
    DEVICE_BASED   = 0x33
    REMOTE_CONTROL = 0x3c
    AP_CONTROLLER  = 0x55


class ActiveBasalRateDelivery:
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
        self.active_basal_rate_profile_template_number: int | None = None
        self.active_basal_rate_current_config_value: float | None = None
        self.tbr_type: TBRType | None = None
        self.tbr_adjustment_value: float | None = None
        self.tbr_duration_programmed: int | None = None
        self.tbr_duration_remaining: int | None = None
        self.tbr_template_number: int | None = None
        self.basal_delivery_context: BasalDeliveryContext | None = None

    def parse(self) -> bool:
        # minimal length is the size of the mandatory fields plus, optionally,
        # 3 bytes for the E2E-Counter and E2E-CRC
        min_length = 8
        if self.use_e2e:
            min_length += 3

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
        opcode,     data = ParseUtils.consume_u16(data)
        self.flags, data = ParseUtils.consume_u8(data)
        self.active_basal_rate_profile_template_number, data = ParseUtils.consume_u8(data)
        self.active_basal_rate_current_config_value,    data = ParseUtils.consume_f32(data)

        expected_opcode = IddStatusReaderOpCode.GET_ACTIVE_BASAL_RATE_DELIVERY_RESPONSE
        if opcode != expected_opcode:
            self.logger.error("Wrong response opcode: 0x%04x, wanted 0x%04x"
                % (opcode, expected_opcode))
            return False

        # TBR (optional)
        if self.flags & ActiveBasalRateFlags.TBR_PRESENT:
            self.tbr_type,                data = ParseUtils.consume_u8(data)
            self.tbr_adjustment_value,    data = ParseUtils.consume_f32(data)
            self.tbr_duration_programmed, data = ParseUtils.consume_u16(data)
            self.tbr_duration_remaining,  data = ParseUtils.consume_u16(data)

            assert TBRType.contains_value(self.tbr_type)
            self.tbr_type = TBRType(self.tbr_type)

        # TBR Template Number (optional)
        if self.flags & ActiveBasalRateFlags.TBR_TEMPLATE_NUMBER_PRESENT:
            self.tbr_template_number, data = ParseUtils.consume_u8(data)

        # Basal Delivery Context (optional)
        if self.flags & ActiveBasalRateFlags.BASAL_DELIVERY_CONTEXT_PRESENT:
            self.basal_delivery_context, data = ParseUtils.consume_u8(data)

            print(f"{self.basal_delivery_context:02x}")

            assert BasalDeliveryContext.contains_value(self.basal_delivery_context)
            self.basal_delivery_context = BasalDeliveryContext(self.basal_delivery_context)

        # we are done, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self) -> str:
        flags = ParseUtils.parse_flags(self.flags, ActiveBasalRateFlags)
        flag_list = ", ".join([f.name for f in flags])

        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                                     "
                + ("--" if (self.flags is None or not flag_list) else flag_list),
            f"Active Basal Rate Profile Template Number: "
                + ("--" if self.active_basal_rate_profile_template_number is None else f"{self.active_basal_rate_profile_template_number}"),
            f"Active Basal Rate Current Config Value:    "
                + ("--" if self.active_basal_rate_current_config_value is None else f"{self.active_basal_rate_current_config_value} IU/h"),
            f"TBR Type:                                  "
                + ("--" if self.tbr_type is None else self.tbr_type.name),
            f"TBR Adjustment Value:                      "
                + ("--" if self.tbr_adjustment_value is None else f"{self.tbr_adjustment_value} IU/h"),
            f"TBR Duration Programmed:                   "
                + ("--" if self.tbr_duration_programmed is None else f"{self.tbr_duration_programmed} min"),
            f"TBR Duration Remaining                     "
                + ("--" if self.tbr_duration_remaining is None else f"{self.tbr_duration_remaining} min"),
            f"TBR Template Number:                       "
                + ("--" if self.tbr_template_number is None else f"{self.tbr_template_number}"),
            f"Basal Delivery Context:                    "
                + ("--" if self.basal_delivery_context is None else self.basal_delivery_context.name),
        ]) + "\n)"


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    raw = bytes.fromhex("6a03000200000000")
    data = ActiveBasalRateDelivery(raw)
    if data.parse():
        print(data)
    else:
        print("Failed to parse Active Basal Rate Delivery")

