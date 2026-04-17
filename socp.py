from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time
from enum import IntEnum

from log_manager import LogManager
from sake_handler import SakeHandler
from value_converter import ValueConverter
from uuids import UUID

from socp_opcodes import SocpOpCode
from sensor_details import SensorDetails


class SocpController():

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central
        self.resp_received = threading.Event()
        self.last_value:bytes|None = None
        self.sh = SakeHandler()
        self._configure_characteristics()
        return
    
    def unsubscribe(self):
        self.socp_char.add_characteristic_cb(None)
        return
    
    def _configure_characteristics(self):
        self.logger.debug("Adding SOCP char")
        self.socp_char = self.central.add_characteristic(UUID.CGM_SERVICE, UUID.CGM_SOCP_CHAR)
        while not self.socp_char.resolve_gatt():
            time.sleep(0.2)
        self.logger.debug(f"socp char flags = {self.socp_char.flags}")
        assert "write" in dbus_tools.dbus_to_python(self.socp_char.flags)
        self.socp_char.add_characteristic_cb(self._socp_cb)
        self.logger.debug("_socp_cb() added")
        self.socp_char.start_notify()
        self.logger.debug("socp notifications enabled")
        return
    
    def _read_session_id(self) -> int | None:
        raise NotImplementedError()
        # NOTE! this is not supported on the pump, only the sensor (?) 

        # 1c 8c 02 2984
        # 1c .. .. ....  Op Code: Response Code
        # .. 8c .. ....  Operand: Request Op Code: Read Current Session ID
        # .. .. 02 ....  Operand: Response Code Value: Op Code not supported
        # .. .. .. 2984  E2E-CRC

        raw = self._trigger_opcode(SocpOpCode.READ_CURRENT_SESSION_ID)
        data = self._check_and_get_resp(raw, SocpOpCode.READ_CURRENT_SESSION_ID_RESPONSE)     
        toret = int.from_bytes(data, byteorder="little") # TODO: endianness?
        return toret
    
    def _read_session_start(self, session_id:int) -> None:
        raise NotImplementedError()
        # NOTE: this is not supported on the pump, only the sensor (?) 
        # buildReadSessionStartTimeRequest() is never called by the Minimed app.
        # dies with Operation failed with ATT error: 0x80 (Application Error ???)
        id = int.to_bytes(session_id, length=2, byteorder="little")
        raw = self._trigger_opcode(SocpOpCode.READ_SESSION_START_TIME, id)
        data = self._check_and_get_resp(raw, SocpOpCode.READ_SESSION_START_TIME_RESPONSE)
        self.logger.debug(f"read session start time = {data.hex()}")
        return
    
    def read_sensor_details(self) -> None:
        raw = self._trigger_opcode(SocpOpCode.GET_SENSOR_DETAILS)
        data = self._check_and_get_resp(raw, SocpOpCode.SENSOR_DETAILS_RESPONSE)
        # NOTE: we pass the *raw* data since we compute the CRC as part of the
        #       parsing
        obj = SensorDetails(raw, use_e2e=True)
        if obj.parse():
            self.logger.debug(obj)
        else:
            self.logger.error("Failed to parse Sensor Details")
        return

    def _check_and_get_resp(self, raw:bytes, expected:SocpOpCode) -> bytes:
        code = raw[0]
        raw = raw[1:]
        if code != expected.value:
            raise ValueError(f"Invalid opcode received ({hex(code)}), expected = {hex(expected.value)}")
        return raw
    
    def _trigger_opcode(self, opcode:SocpOpCode, extra_data:None|bytes=None, timeout:int=3) -> bytes | None:

        self.resp_received = threading.Event()
        self.last_value = None

        req = bytes([opcode.value])
        if extra_data:
            req += extra_data
        crc = ValueConverter.e2e_crc(req)
        crc = crc.to_bytes(2, "little")
        req += crc

        ciph = self.sh.server.session.server_crypt.encrypt(req)
        self.logger.debug(f"writing {req.hex()} (encrypted: {ciph.hex()}) to socp...")
        self.socp_char.write_value(list(ciph))

        if self.resp_received.wait(timeout=timeout):
            self.logger.debug("Resp received")
            assert self.last_value != None
            toret = self.last_value
            self.last_value = None
            return toret
    
        else:
            self.logger.debug("timeout")

        return None

    def _socp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            ciph = bytes(dbus_tools.dbus_to_python(changed_props["Value"]))
            self.logger.debug("SOCP callback: " + ciph.hex())
            self.last_value = self.sh.server.session.server_crypt.decrypt(ciph)
            self.resp_received.set()
        return
