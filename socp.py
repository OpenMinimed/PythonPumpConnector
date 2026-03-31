from bluezero import dbus_tools
from bluezero.central import Central

#import threading
import time

#from cgm_measurement import CGMMeasurement
from log_manager import LogManager

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sake_handler import SakeHandler

from cgm_measurement import CGMMeasurement
from sg_reader import UUID_CGM_SERVICE

UUID_SOCP_CHAR        = "00002aac-0000-1000-8000-00805f9b34fb"

# get sensor details: 1717274581169,sake,encrypt,90 4962 (3 bytes raw);896d0a09cc8f (6 bytes encrypted)


class SocpController:

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        #self.cgm_measurement = None
        #self.cgm_racp        = None

        #self.measurement_received = threading.Event()
        #self.operation_finished   = threading.Event()
        self.last_value:bytes   = None
        #self.response = None

        #success = self._configure_characteristics()
        #assert success == True
        self.logger.debug("Adding SOCP char")
        self.socp_char = self.central.add_characteristic(UUID_CGM_SERVICE, UUID_SOCP_CHAR)
        while not self.socp_char.resolve_gatt():
            time.sleep(0.2)
        
       # assert "notify" in dbus_tools.dbus_to_python(self.socp_char.flags)
        self.logger.debug(f"socp char flags = {self.socp_char.flags}")
        
        self.socp_char.add_characteristic_cb(self._socp_cb)
        self.logger.debug("_socp_cb() added")
        self.socp_char.start_notify()
        self.logger.debug("socp notifications enabled")
        return

    def trigger_session_id(self, sh:"SakeHandler"):
        req = bytes([0x8c])
        crc = CGMMeasurement.e2e_crc(req)
        crc = crc.to_bytes(2, "little")
        req = req + crc
        
        req = bytes.fromhex("904962")
        ciph = sh.server.session.server_crypt.encrypt(req)
        self.logger.debug(f"writing {req.hex()} (encrypted: {ciph.hex()}) to scp...")
       
        # NOTE: if you send wrongly encrypted data here, you will get 20 zero bytes on sake char. if you dont re-handshake in 5seconds you will get a disconnect???
        try:
            dec = sh.server.session.client_crypt.decrypt(ciph)
            self.logger.debug(f"client decrypted = {dec.hex()}")
        except Exception as e:
            self.logger.warning(f"client dec failed! {e}")

        self.socp_char.write_value(list(ciph))
        return

    def _socp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            self.last_value = bytes(dbus_tools.dbus_to_python(changed_props["Value"]))
            self.logger.debug("SOCP callback: " + self.last_value.hex())



if __name__ == "__main__":
    req = bytes([0x8d, 0x0c])
    crc = CGMMeasurement.e2e_crc(req)
    crc = crc.to_bytes(2, "little")
    req = req + crc
    print(req.hex()) # is 904962, so its good


    # 1701206239919,sake,encrypt,8cf4b1;954ba803d8f8
    # 1701206239986,bt,write,00002aac-0000-1000-8000-00805f9b34fb;954ba803d8f8
    # 1701206239992,bt,notify,00002aac-0000-1000-8000-00805f9b34fb;72b745490332cd
    # 1701206239996,sake,decrypt,72b745490332cd;8d 0b a0 c1

    SESS_ID_RESP_OPCODE = 0x8d 
    # on the cgm transmitter it is 1 byte opcode, 1 byte id, 2 byte crc
    #bytes.fromhex("8d 0b a0 c1")

    # mmm receives: CALIBRATION_CONTEXT_RESPONSE, SENSOR_DETAILS_RESPONSE

    # 81fffff9dd (GET_CALIBRATION_CONTEXT)
    # 82020000f0da (CALIBRATION_CONTEXT_RESPONSE)

    # 904962 (GET_SENSOR_DETAILS)
    # 91071d00ffff60273420 (SENSOR_DETAILS_RESPONSE)

    # 05ffff633a perhaps ????