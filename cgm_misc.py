from bluezero import dbus_tools
from bluezero.central import Central

import time

from log_manager import LogManager

from value_converter import ValueConverter
from sake_handler import SakeHandler
from sg_reader import UUID_CGM_SERVICE

UUID_RUN_TIME_CHAR = "00002aab-0000-1000-8000-00805f9b34fb"
UUID_STAR_TIME_CHAR = "00002aaa-0000-1000-8000-00805f9b34fb"

class CgmMiscData:

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central
        self.sh = SakeHandler()
        self._configure_characteristics()
        self.run_time_char = None
        self.start_time_char = None
        return
    
    def read_run_time(self) -> None | int:
    
        read = self.run_time_char.read_raw_value()
        if read is None:
            return None
        read = bytes(read)
       # self.logger.debug(f"read raw on cgm run time = {read.hex()}")
       
        if not ValueConverter.check_crc(read):
            self.logger.error(f"crc mismatch!")
            return None

        data = read[:2]
        toret = int.from_bytes(data, byteorder="little")

        self.logger.debug(f"final run time = {toret}")
        return toret
    
    def read_start_time(self) -> None: # TODO: return type
        read = self.start_time_char.read_raw_value()
        if read is None:
            return None
        read = bytes(read)
        self.logger.debug(f"read raw on cgm start time = {read.hex()}")
        plain = self.sh.server.session.server_crypt.decrypt(read)
        # plain = ea07031c0a1f2a80ff 0873
        if not ValueConverter.check_crc(plain):
            self.logger.error("crc mismatch on start time!")
            return None
        data = plain[0:-2]
        self.logger.debug(f"unparsed start time = {data.hex()}")
        # TODO: parse it properly

        return None
   
    def _configure_characteristics(self):

        self.run_time_char = self.central.add_characteristic(
            UUID_CGM_SERVICE, UUID_RUN_TIME_CHAR)
        while not self.run_time_char.resolve_gatt():
            time.sleep(0.2)
        assert "read" in dbus_tools.dbus_to_python(self.run_time_char.flags)

        self.start_time_char = self.central.add_characteristic(
            UUID_CGM_SERVICE, UUID_STAR_TIME_CHAR)
        while not self.start_time_char.resolve_gatt():
            time.sleep(0.2)
        assert "read" in dbus_tools.dbus_to_python(self.start_time_char.flags)
        
        return