from bluezero import dbus_tools
from bluezero.central import Central

import time
from datetime import datetime, timedelta, timezone

from log_manager import LogManager

from parse_utils import ParseUtils
from value_converter import ValueConverter
from sake_handler import SakeHandler
from uuids import UUID


class CgmStartTime():

    ts_raw:datetime = None
    ts_final:datetime = None
    timeZoneOffset:int = None
    dstOffset:int| None = None
    raw:bytes = None

    def __init__(self, raw:bytes):
        self.raw = raw

        # see section 3.45 "CGM Session Start Time" of the GATT Specification
        # Supplement (GSS), Bluetooth® Document, 2025-12-23

        self.ts_raw, raw = ParseUtils.consume_datetime(raw)
        tz,          raw = ParseUtils.consume_i8(raw)
        dst,         raw = ParseUtils.consume_u8(raw)

        if tz != -128: # time zone offset must no be unknown
            self.timeZoneOffset = tz * 15

        if dst != 0xff: # DST offset must not be unknown
            self.dstOffset = dst * 15

        self.ts_final = self.__apply_cgm_offsets()

    def __apply_cgm_offsets(self):

        total_offset_min = 0

        if self.timeZoneOffset is not None:
            total_offset_min += self.timeZoneOffset

        if self.dstOffset is not None:
            total_offset_min += self.dstOffset

        delta = timedelta(minutes=total_offset_min)

        return self.ts_raw + delta

        
    def __format(self, stamp) -> str:
        return stamp.strftime('%Y-%m-%d %H:%M:%S')
        
    def __str__(self):
        return f"CgmStartTime({self.raw.hex() = }, {self.timeZoneOffset = }, {self.dstOffset = }, raw ts = {self.__format(self.ts_raw)}, final ts = {self.__format(self.ts_final)} )"
    

class CgmMiscData:

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central
        self.sh = SakeHandler()
        self.run_time_char = None
        self.start_time_char = None
        self._configure_characteristics()
        return
    
    def unsubscribe(self):
        # intentionally empty, since we have no callbacks!
        return

    def read_run_time(self) -> None | int:
    
        read = self.run_time_char.read_raw_value()
        if read is None:
            return None
        read = bytes(read)
       
        if not ValueConverter.check_crc(read):
            self.logger.error(f"crc mismatch!")
            return None

        data = read[:2]
        toret = int.from_bytes(data, byteorder="little")

        self.logger.info(f"final run time = {toret}")
        return toret
    
    def read_start_time(self) -> datetime:
        read = self.start_time_char.read_raw_value()
        if read is None:
            return None
        read = bytes(read)
        self.logger.debug(f"read raw on cgm start time = {read.hex()}")
        plain = self.sh.server.session.server_crypt.decrypt(read)
        if not ValueConverter.check_crc(plain):
            self.logger.error("crc mismatch on start time!")
            return None
        data = plain[0:-2]
        o = CgmStartTime(data)
        self.logger.info(f"read start time = {o}")
        return o.ts_final
    
    def calc_remaining_time(self) -> float:
        rt = self.read_run_time()
        st = self.read_start_time()

        delta = timedelta(hours=rt)
        end = st + delta

        toret = end - datetime.now()
        toret_hours = toret.total_seconds() / 3600
        hours = int(toret_hours)
        minutes = int((toret_hours - hours) * 60)
        self.logger.info(f"remaining time until sensor expires = {hours}:{minutes:02d}")
        return toret_hours
        

    def _configure_characteristics(self):

        self.run_time_char = self.central.add_characteristic(
            UUID.CGM_SERVICE, UUID.CGM_SESSION_RUN_TIME_CHAR)
        while not self.run_time_char.resolve_gatt():
            time.sleep(0.2)
        assert "read" in dbus_tools.dbus_to_python(self.run_time_char.flags)

        self.start_time_char = self.central.add_characteristic(
            UUID.CGM_SERVICE, UUID.CGM_SESSION_START_TIME_CHAR)
        while not self.start_time_char.resolve_gatt():
            time.sleep(0.2)
        assert "read" in dbus_tools.dbus_to_python(self.start_time_char.flags)
        
        return
    
if __name__  == "__main__":
    from utils import add_submodule_to_path
    add_submodule_to_path()

    test = bytes.fromhex("ea0704040c323680ff")
    t = CgmStartTime(test)
    print(t)