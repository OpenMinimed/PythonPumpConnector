import logging

from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter

from idd.status.tas_flags import *
from idd.status.opcodes import IddStatusReaderOpCode


class TherapyAlgorithmStatesData:


    def __init__(self, data: bytes, use_e2e: bool = False):

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data
        self.use_e2e = use_e2e

        # parsed data
        self.flags: int | None = None
        self.auto_mode_shield_state: AutoModeShieldState | None = None
        self.auto_mode_readiness_state: AutoModeReadinessState | None = None
        self.plgm_state: PlgmOrLgsState | None = None
        self.lgs_state: PlgmOrLgsState | None = None
        self.temp_target_duration: int | None = None
        self.wait_to_calibrate_duration: int | None = None
        self.safe_basal_duration: int | None = None
     
        return

    def parse(self) -> bool:
        # minimal length is the size of the mandatory fields plus, optionally,
        # 3 bytes for the E2E-Counter and E2E-CRC
        min_length = 18 if self.use_e2e else 3

        data = self.data
        length = len(data)

        # if length < min_length:
        #     self.logger.error("Packet too short: wanted at least %d bytes, got %d"
        #         % (min_length, length))
        #     return False

        #validate E2E-CRC
        
        #TODO: Actually test this! This was not yet tested since the pump
        #      never uses E2E-Protection in this service.
        if self.use_e2e:
            if not ValueConverter.check_crc(data):
                self.logger.error("E2E-CRC mismatch")
                return False

            # snip CRC
            data = data[:-2]

            # snip E2E-Counter (we had to keep it until now because it must be
            # included in the CRC)
            data = data[:-1]

        opcode, data = ParseUtils.consume_u16(data)

        if opcode != IddStatusReaderOpCode.GET_THERAPY_ALGORITHM_STATES_RESPONSE:
            self.logger.error(f"invalid opcode, expected {hex(IddStatusReaderOpCode.GET_THERAPY_ALGORITHM_STATES_RESPONSE)}, got {hex(opcode)}")
            return False

        self.flags, data = ParseUtils.consume_u16(data)
        self.logger.debug(f"{hex(self.flags) = }, {hex(opcode) = }")

        if self.flags & TherapyAlgorithmStatesFlags.AUTO_MODE:
            x, data = ParseUtils.consume_u8(data)
            self.auto_mode_shield_state = AutoModeShieldState(x)

            x, data = ParseUtils.consume_u8(data)
            self.auto_mode_readiness_state = AutoModeReadinessState(x)

        if self.flags & TherapyAlgorithmStatesFlags.PLGM_OPTION:
            x, data = ParseUtils.consume_u8(data)
            self.plgm_state = PlgmOrLgsState(x)

        if self.flags & TherapyAlgorithmStatesFlags.LGS_OPTION:
            x, data = ParseUtils.consume_u8(data)
            self.lgs_state = PlgmOrLgsState(x)

        if self.flags & TherapyAlgorithmStatesFlags.TEMP_TARGET:
            self.temp_target_duration, data = ParseUtils.consume_u16()

        if self.flags & TherapyAlgorithmStatesFlags.WAIT_TO_CALIBRATE:
            self.wait_to_calibrate_duration, data = ParseUtils.consume_u16()

        if self.flags & TherapyAlgorithmStatesFlags.SAFE_BASAL:
            self.safe_basal_duration, data = ParseUtils.consume_u8()

        # we are done, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self) -> str:
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Flags:                      "
                + ("--" if self.flags is None else f"{self.flags:019_b}".replace("0", ".").replace("_", " ")),
            f"Auto Mode Shield State:     "
                + ("--" if self.auto_mode_shield_state is None else self.auto_mode_shield_state.name),
            f"Auto Mode Readiness State:  "
                + ("--" if self.auto_mode_readiness_state is None else self.auto_mode_readiness_state.name),
            f"PLGM State:                 "
                + ("--" if self.plgm_state is None else self.plgm_state.name),
            f"LGS State:                  "
                + ("--" if self.lgs_state is None else self.lgs_state.name),
            # TODO: add proper unit
            f"Temp Target Duration:       "
                + ("--" if self.temp_target_duration is None else f"{self.temp_target_duration}"),
            # TODO: add proper unit
            f"Wait to Calibrate Duration: "
                + ("--" if self.wait_to_calibrate_duration is None else f"{self.wait_to_calibrate_duration}"),
            # TODO: add proper unit
            f"Safe Basal Duration:        "
                + ("--" if self.safe_basal_duration is None else f"{self.safe_basal_duration}"),
        ]) + "\n)"


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    raw = bytes.fromhex("fe0301000200")
    data = TherapyAlgorithmStatesData(raw)
    if data.parse():
        print(data)
    else:
        print("Failed to parse")

