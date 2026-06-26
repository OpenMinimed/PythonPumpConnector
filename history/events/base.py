import logging

from utils.log_manager import LogManager
from utils.parse_utils import ParseUtils


class HistoryEventData:
    def __init__(self, data: bytes):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self._raw = data

    def parse(self) -> bool:
        success, data = self._parse_impl(self._raw)
        if not success:
            return False

        if len(data) > 0:
            self.logger.error("Extra event data after parsing: "
                + "%d byte(s) left, should be 0"  % len(data))
            return False

        return True

    def _parse_impl(self, data) -> tuple[bool, bytes]:
        return False, data

    @staticmethod
    def _pp(x, unit=""):
        if unit:
            unit = " " + unit
        return "--" if x is None else f"{x}{unit}"

    @staticmethod
    def _pp_flags(x):
        return f"{x:09_b}".replace("0", ".").replace("_", " ")

    @staticmethod
    def _pp_flag_list(x, flag_type):
        flags = ParseUtils.parse_flags(x, flag_type)
        return ", ".join([f.name for f in flags])


class UnknownEventData(HistoryEventData):
    def __init__(self, data: bytes):
        super().__init__(data)

    def _parse_impl(self, data):
        return True, []

    def __str__(self):
        return "\n    ".join([
            f"{self.__class__.__name__}(",
            f"# TODO: implement handler for this event type",
            f"Data: {self._raw.hex()}",
        ]) + "\n)"