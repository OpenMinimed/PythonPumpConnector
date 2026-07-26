from bluezero import dbus_tools
from bluezero.central import Central

import threading
import time

from utils.gatt import GATTBase
from utils.log_manager import LogManager
from utils.uuids import UUID


class HATS(GATTBase):
    """
    History And Trace Service
    """

    def __init__(self, central:Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.hat_slice_record = None
        self.hat_rtmcp        = None
        self.hat_rmcpse       = None
        self.hat_racp         = None

        success = self._configure_characteristics()
        assert success == True

    def unsubscribe(self):
        self.hat_slice_record.add_characteristic_cb(None)
        self.hat_rtmcp.add_characteristic_cb(None)
        self.hat_rmcpse.add_characteristic_cb(None)
        self.hat_racp.add_characteristic_cb(None)
        return

    def send_request(self):
        ## RTMCP char

        # Opcode:           0x02 (Repository Request)
        # Request Type:     0x01 (Transactional Request)
        # Control Flags:    0x00
        # Device Source ID: 0x00000000
        # History Type:     0x00 (Repository List)
        # Instance ID:      0x00
        # Token Type:       0x00 (Absolute Reference)
        # Start Index:      u32
        # End Index:        u32
        #self.hat_rtmcp.write_value([
        #    0x02,
        #    0x01,
        #    0x00,
        #    0x00,0x00,0x00,0x00,
        #    0x00,
        #    0x00,
        #    0x00,
        #    0x00,0x00,0x00,0x00,
        #    0x10,0x00,0x00,0x00
        #])
        # -> responds with RTMCP indication:
        #     01 02 01
        #     01 .. ..  Opcode: Response Code
        #     .. 02 ..  Request Opcode: Repository Request
        #     .. .. 01  Response Code Value: Opcode Not Supported

        # Opcode:           0x05 (Get Repository Request Status)
        self.hat_rtmcp.write_value([0x05])
        # -> responds with RTMCP indication:
        #     03 00 03
        #     03 .. ..  Opcode: Repository Request Status Response
        #     .. 00 ..  Operand: Repository Status Flags
        #     .. .. 03  Operand: Repository Request Status: Transfer Session Expired

        # Opcode:           0x07 (Get Slice Transport Parameters)
        #self.hat_rtmcp.write_value([0x07])
        # -> responds with RTMCP indication:
        #     09 1200
        #     09 ....  Opcode: Slice Transport Parameters Response
        #     .. 1200  Operand: Slice Size: 18

        # Opcode:           0x0a (Get Transfer Block Parameters)
        #self.hat_rtmcp.write_value([0x0a])
        # -> responds with RTMCP indication:
        #     0c 00 00
        #     0c .. ..  Opcode: Transfer Block Parameter Response
        #     .. 00 ..  Operand: Compression Setting: None
        #     .. .. 00  Operand: Encryption Setting: None

        # Opcode:            0x0e (Get Session Metrics)
        # Session Metric ID: 0x00
        #self.hat_rtmcp.write_value([0x0e, 0x00])
        # -> responds with RTMCP indication:
        #     0f 00 ffffffff ffffffff
        #     0f .. ........ ........  Opcode: Session Metrics Response
        #     .. 00 ........ ........  Operand: Session Metric ID
        #     .. .. ffffffff ........  Operand: Compression Time: Invalid
        #     .. .. ........ ffffffff  Operand: Encryption Time: Invalid


        ## RMCP SE char

        # Opcode:           0xa2 (Secure Repository Request)
        # Request Type:     0x01 (Transactional Request)
        # Control Flags:    0x00
        # Token Size:       0x00
        # Token Bytes:      --
        #self.hat_rmcpse.write_value([0xa2, 0x01, 0x00, 0x00])
        # -> responds with RMCP SE indication:
        #     01 a2 02
        #     01 .. ..  Opcode: Response Code
        #     .. a2 ..  Request Opcode: Secure Repository Requst
        #     .. .. 02  Response Code Value: Invalid Operand

        # Opcode:           0xa2 (Secure Repository Request)
        # Request Type:     0x01 (Transactional Request)
        # Control Flags:    0x00
        # Token Size:       0x01
        # Token Bytes:      0x00
        #self.hat_rmcpse.write_value([0xa2, 0x01, 0x00, 0x01, 0x00])
        # -> responds with *RTMCP* (not RMCP SE!) indication:
        #     03 00 07
        #     03 .. ..  Opcode: Repository Request Status Response
        #     .. 00 ..  Repository Status Flags
        #     .. .. 07  Repository Request Status: Secure Session Unavailable


        ## RACP char

        # Opcode:   0x01 (Report Stored Records)
        # Operator: 0x06 (Last Record)
        #self.hat_racp.write_value([0x01, 0x06])
        # -> responds with RACP indication:
        #     06 00 01 06
        #     06 .. .. ..  Opcode: SliceRacpOpCode.RESPONSE_CODE
        #     .. 00 .. ..  ignored
        #     .. .. 01 ..  Request Opcode: SliceRacpOpCode.REPORT_STORED_RECORDS
        #     .. .. .. 06  Operand: SliceRacpResponseCode.NO_RECORDS_FOUND

    def _configure_characteristics(self):
        # HAT service, Slice Record characteristic
        self.hat_slice_record = self._add_char(UUID.HAT_SERVICE, UUID.HAT_CHAR_SLICE_RECORD,
            ["notify"], callback=self._slice_record_cb)
        if self.hat_slice_record is None:
            return False

        # HAT service, RTMCP characteristic
        self.hat_rtmcp = self._add_char(UUID.HAT_SERVICE, UUID.HAT_CHAR_RTMCP,
            ["write", "indicate"], callback=self._rtmcp_cb)
        if self.hat_rtmcp is None:
            return False

        # HAT service, RMCPSE characteristic
        self.hat_rmcpse = self._add_char(UUID.HAT_SERVICE, UUID.HAT_CHAR_RMCPSE,
            ["write", "indicate"], callback=self._rmcpse_cb)
        if self.hat_rmcpse is None:
            return False

        # HAT service, RACP characteristic
        self.hat_racp = self._add_char(UUID.HAT_SERVICE, UUID.HAT_CHAR_RACP,
            ["write", "indicate"], callback=self._racp_cb)
        if self.hat_racp is None:
            return False

        return True

    def _slice_record_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("Slice Record notification: " + value.hex())

    def _rtmcp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("RTMCP indication: " + value.hex())

    def _rmcpse_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("RMCP SE indication: " + value.hex())

    def _racp_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("RACP indication: " + value.hex())

