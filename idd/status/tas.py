import logging

from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter

from idd.status.tas_flags import *
from idd.status.opcodes import IddStatusReaderOpCode


class TherapyAlgorithmStates:


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
        parts = [
            f"{self.__class__.__name__} Flags: {self.flags:#06x}" if self.flags is not None else "Flags: None",
        ]
        
        if self.auto_mode_shield_state is not None:
            parts.append(f"Auto Mode Shield State: {self.auto_mode_shield_state.name}")
        
        if self.auto_mode_readiness_state is not None:
            parts.append(f"Auto Mode Readiness State: {self.auto_mode_readiness_state.name}")
        
        if self.plgm_state is not None:
            parts.append(f"PLGM State: {self.plgm_state.name}")
        
        if self.lgs_state is not None:
            parts.append(f"LGS State: {self.lgs_state.name}")
        
        if self.temp_target_duration is not None:
            parts.append(f"Temp Target Duration: {self.temp_target_duration}")
        
        if self.wait_to_calibrate_duration is not None:
            parts.append(f"Wait to Calibrate Duration: {self.wait_to_calibrate_duration}")
        
        if self.safe_basal_duration is not None:
            parts.append(f"Safe Basal Duration: {self.safe_basal_duration}")
        
        return "\n  ".join(parts)


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    raw = bytes.fromhex("fe0301000200")
    data = TherapyAlgorithmStates(raw)
    if data.parse():
        print(data)
    else:
        print("Failed to parse")

