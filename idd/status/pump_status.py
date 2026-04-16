import logging

from base_enum import BaseEnum
from log_manager import LogManager
from parse_utils import ParseUtils
from value_converter import ValueConverter


class TherapyControlState(BaseEnum):
    UNDETERMINED = 0x0f
    STOP         = 0x33
    PAUSE        = 0x3c
    RUN          = 0x55


class OperationalState(BaseEnum):
    UNDETERMINED = 0x0f
    OFF          = 0x33
    STANDBY      = 0x3c
    PREPARING    = 0x55
    PRIMING      = 0x5a
    WAITING      = 0x66
    READY        = 0x96


class IDDStatusFlag(BaseEnum):
    RESERVOIR_ATTACHED = 1<<0


class SensorConnectivityState(BaseEnum):
    SENSOR_ON           = 1<<0
    SENSOR_PAIRED       = 1<<1
    GST_SIGNAL_LOST     = 1<<2
    SENSOR_GST_DETACHED = 1<<3


class SensorMessageState(BaseEnum):
    NO_MESSAGE                  = 0x00
    WAIT_TO_CALIBRATE           = 0x01
    DO_NOT_CALIBRATE            = 0x02
    CALIBRATION_REQUIRED        = 0x03
    CALIBRATING                 = 0x04
    SEARCHING_FOR_SENSOR_SIGNAL = 0x05
    NO_SENSOR_SIGNAL            = 0x06
    CHANGE_SENSOR               = 0x07
    WARM_UP                     = 0x08
    SG_BELOW_LOWER_LIMIT        = 0x09
    SG_ABOVE_UPPER_LIMIT        = 0x0a
    GST_BATTERY_DEPLETED        = 0x0b
    SENSOR_CONNECTED            = 0x0c
    WAITING_WARM_UP             = 0x0d
    NO_PAIRED_SENSOR            = 0x0e


class PumpStatus:
    def __init__(self, data: bytes, use_e2e: bool = False):
        """
        :param data:    The raw data
        :param use_e2e: Whether to assume E2E-Counter and E2E-CRC are included in the data
        """

        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.data = data
        self.use_e2e = use_e2e

        # parsed data
        self.therapy_control_state: TherapyControlState | None = None
        self.operational_state: OperationalState | None = None
        self.reservoir_remaining_amount: float | None = None
        self.flags: list[IDDStatusFlag] | None = None
        self.sensor_connectivity_state: list[SensorConnectivityState] | None = None
        self.sensor_message_state: SensorMessageState | None = None

    def is_reservoir_attached(self) -> None | bool:
        if self.flags is None:
            return None
        return IDDStatusFlag.RESERVOIR_ATTACHED in self.flags

    def parse(self) -> bool:
        expected_length = 9
        if self.use_e2e:
            expected_length += 3

        data = self.data
        length = len(data)

        if length != expected_length:
            self.logger.error("Unexpected length: wanted %d bytes, got %d"
                % (expected_length, length))
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

        self.therapy_control_state,      data = ParseUtils.consume_u8(data)
        self.operational_state,          data = ParseUtils.consume_u8(data)
        self.reservoir_remaining_amount, data = ParseUtils.consume_f32(data)

        x,                               data = ParseUtils.consume_u8(data)
        self.flags                            = ParseUtils.parse_flags(x, IDDStatusFlag)
        
        y,                               data = ParseUtils.consume_u8(data)
        self.sensor_connectivity_state        = ParseUtils.parse_flags(y, SensorConnectivityState)

        self.sensor_message_state,       data = ParseUtils.consume_u8(data)

        assert TherapyControlState.contains_value(self.therapy_control_state)
        self.therapy_control_state = TherapyControlState(self.therapy_control_state)

        assert OperationalState.contains_value(self.operational_state)
        self.operational_state = OperationalState(self.operational_state)

        assert SensorMessageState.contains_value(self.sensor_message_state)
        self.sensor_message_state = SensorMessageState(self.sensor_message_state)

        # we are done, there must not be any data left
        if len(data) > 0:
            self.logger.error("Extra data in record: %d byte(s) left, should be 0"
                % len(data))
            return False

        return True

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"Therapy Control State:      "
                + ("--" if self.therapy_control_state is None else self.therapy_control_state.name),
            f"Operational State:          "
                + ("--" if self.operational_state is None else self.operational_state.name),
            f"Reservoir Remaining Amount: "
                + ("--" if self.reservoir_remaining_amount is None else f"{self.reservoir_remaining_amount} Unit"),
            f"Flags:                      "
                + ("--" if self.flags is None else f"{self.flags}"),
            f"Sensor Connectivity State:  "
                + ("--" if self.sensor_connectivity_state is None else f"{self.sensor_connectivity_state}"),
            f"Sensor Message State:       "
                + ("--" if self.sensor_message_state is None else self.sensor_message_state.name),
        ]) + "\n)"


if __name__ == "__main__":
    LogManager.init(level=logging.DEBUG)

    raw = bytes.fromhex("5596e80d28fb010300")
    data = PumpStatus(raw)
    if data.parse():
        print(data)
    else:
        print("Failed to parse pump status")

