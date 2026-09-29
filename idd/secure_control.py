import struct
import threading

from bluezero import dbus_tools
from bluezero.central import Central

from ble.sake import SakeHandler
from utils.gatt import GATTBase
from utils.log_manager import LogManager
from utils.uuids import UUID


class SecureControlOpCode:
    SEND_DATA = 1
    CONFIRM_DATA = 2


class ConfirmDataStatus:
    VALID_KEY_DATA = 0
    INVALID_KEY_DATA = 1


class SecureControlPoint(GATTBase):
    """
    IDD Secure Control Point (0x0109). Only ever used by the app during the
    passkey/SRP-6a (protocol v2) pairing flow, right after the SAKE
    handshake succeeds -- reverse engineered from the app's
    PublicKeyExchangeApiImpl (od.C8718d), called from
    ge.C6639x2.m22029j2/m22030j3 immediately after
    useSakeProtocolV2()+performHandshake(). A normal v1 reconnect never
    calls mo26681a (the only caller in the whole app), so it never touches
    this characteristic -- confirmed via xrefs, not assumed.

    Wire format (all fields little-endian), reverse engineered from
    p315qd.SecureControlRequestConverter / SecureControlResponseConverter
    and sd.SecureControlOpCode / ConfirmDataStatus:

      Send Data (app -> pump), written to the characteristic:
        u8  opcode = 0x01 (SEND_DATA)
        u16 exchange_id      -- increments by 1 each request, starts at 1
        ... key bytes        -- the real app currently sends 72 zero bytes
                                 (see idd-service.md's Secure Control Point
                                 section); this is presumably a placeholder
                                 in the shipped app rather than a real key

      Confirm Data (pump -> app), indicated back:
        u8  opcode = 0x02 (CONFIRM_DATA)
        u16 exchange_id      -- echoes the request's
        u8  status           -- 0x00 = valid, 0x01 = invalid

    This mirrors what the app itself sends/parses (no live capture against
    a real pump has confirmed it directly) -- it's the best evidence
    available short of that.

    Like the other "SAKE-encrypted" IDS characteristics, the payload above
    is wrapped in the session's SeqCrypt before writing / after reading --
    see IDDStatusReader._send_and_receive_opcode (idd/status/reader.py) for
    the same encrypt-write-wait-decrypt pattern against a different
    characteristic. The SeqCrypt instance is shared across all SAKE-
    encrypted characteristics for a session, whichever SAKE protocol
    version established it (v1 or v2) -- this class doesn't care which.
    """

    def __init__(self, central: Central):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        self.central = central

        self.char = None
        self.sh = SakeHandler()
        self._exchange_id = 0
        self._operation_finished = threading.Event()
        self._response = None

        success = self._configure_characteristics()
        assert success == True
        return

    def send_public_key(self, key_data: bytes = bytes(72), timeout: float = 30) -> bool:
        """
        Send a public key and wait for the pump's Confirm Data response.
        Returns True if the pump reports the key data valid, False on a
        reported-invalid response, a malformed response, or a timeout.

        key_data defaults to 72 zero bytes, matching what the real app
        currently sends (see the class docstring) -- pass real key bytes
        here once/if the real key exchange semantics are understood.

        timeout defaults to 30s, matching the app's own timeout for this
        exchange (PublicKeyExchangeApiImpl).
        """
        self._exchange_id += 1
        exchange_id = self._exchange_id

        request = struct.pack("<BH", SecureControlOpCode.SEND_DATA, exchange_id) + key_data
        self.logger.debug(f"Sending public key, exchange_id={exchange_id}: {request.hex()}")

        self._operation_finished.clear()
        ciph = self.sh.encrypt(request)
        self.char.write_value(ciph)

        if not self._operation_finished.wait(timeout=timeout):
            self.logger.error("Timeout while waiting for Confirm Data")
            return False

        data = self.sh.decrypt(self._response)
        self._response = None

        if len(data) < 4:
            self.logger.error(f"Confirm Data response too short: {data.hex()}")
            return False

        opcode, resp_exchange_id, status = struct.unpack("<BHB", data[:4])
        if opcode != SecureControlOpCode.CONFIRM_DATA:
            self.logger.error(f"Unexpected opcode in response: 0x{opcode:02x}")
            return False
        if resp_exchange_id != exchange_id:
            self.logger.error(
                f"Exchange ID mismatch: sent {exchange_id}, got {resp_exchange_id}"
            )
            return False

        if status == ConfirmDataStatus.VALID_KEY_DATA:
            self.logger.info("Pump confirmed key data as valid")
            return True
        else:
            self.logger.warning(f"Pump rejected key data, status=0x{status:02x}")
            return False

    def unsubscribe(self):
        self.char.add_characteristic_cb(None)
        return

    def _configure_characteristics(self):
        self.char = self._add_char(
            UUID.IDD_SERVICE, UUID.IDD_CHAR_SECURE_CONTROL,
            ["write", "indicate"], callback=self._char_cb,
        )
        return self.char is not None

    def _char_cb(self, iface, changed_props, invalidated_props):
        if "Value" in changed_props:
            value = dbus_tools.dbus_to_python(changed_props["Value"])
            self.logger.debug("Secure Control Point indication: " + value.hex())
            self._response = bytes(value)
            self._operation_finished.set()
        return
