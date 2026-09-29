"""
Adapts PythonSake's tools/sake_v260_emulate/engine.py -- which runs the
real, unmodified Medtronic libandroid-sake-lib.so (v260) protocol-v2
(passkey/SRP-6a) SAKE server inside an ARM emulator -- to the same
.handshake(value)/.is_done() interface pysake.server.SakeServer (v1)
exposes, so SakeHandler can drive either protocol version identically.

This is the real thing, not a reimplementation: every crypto operation is
whatever the real library computes. See PythonSake's
tools/sake_v260_emulate/README.md for how the protocol was reverse
engineered (three separate cases where Ghidra's decompile actively misread
this library, only resolved by running the real code or reading raw
disassembly).

Permit key material: pysake.constants.KEYDB_PUMP_EXTRACTED (already
extracted from and proven against a real pump for protocol v1) turns out
to already carry everything v2's permit step needs, in full -- no separate
"pump's own secret" required. This was confirmed by reading v1's own real
permit check (pysake/session.py's Session.__check_permit, exercised via
handshake_4_s/handshake_5_c): the SENDER never encrypts its permit at send
time -- it just forwards its own precomputed StaticKeys.handshake_payload
verbatim, wrapped only by the session stream cipher. Only the RECEIVER
does an AES-ECB-decrypt, using the receiver's *own*
permit_decrypt_key/permit_auth_key. That's real, working code, proven
against a real pump.

So handshake_payload is already Medtronic's server having done the
"encrypt our permit under the pump's key" step for us, once, server-side,
when the blob was generated -- we forward the finished ciphertext as-is,
we never need the pump's raw key to produce it ourselves. v2's permit
mechanism (confirmed via this session's native-library RE -- see
PythonSake's README, "Solving the permit exchange") is the same shape,
just with the extra static AES-ECB layer v1 lacks; the same
"forward-what-you-were-given" logic applies. All three fields v2 needs --
permit_decrypt_key, permit_auth_key, handshake_payload -- are already in
KEYDB_PUMP_EXTRACTED, unused by v1, real.

(An earlier version of this module assumed a fourth, separate "pump's own
pair" was needed and would have to be sourced elsewhere -- that assumption
came from a self-test that faked *both* sides of the exchange from
scratch, which does need an invented matching pair for the fake side. It
doesn't apply to real pairing, where the pump supplies its own side
independently, the same way it always has for v1.)
"""
from dataclasses import dataclass
import logging
import os
import sys

from utils.log_manager import LogManager


def _sake_v2_engine_module():
    """
    Import PythonSake's tools/sake_v260_emulate/engine module. Done lazily
    (not at file import time) since it pulls in unicorn/capstone/pyelftools
    and maps+emulates an ARM .so on first import -- no reason to pay that
    cost unless --sake-v2 is actually used.
    """
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "PythonSake",
                      "tools", "sake_v260_emulate")
    d = os.path.abspath(d)
    if not os.path.isdir(d):
        raise FileNotFoundError(f"missing PythonSake submodule checkout at {d}")
    if d not in sys.path:
        sys.path.append(d)
    import engine  # noqa: PLC0415 -- intentionally lazy, see docstring
    return engine


# Device types per pysake.device_types.DeviceType / the real SAKE_DEVICE_TYPE_E.
PUMP_DEVICE_TYPE = 1        # InsulinPump -- plays the SAKE_CLIENT role
CONNECTOR_DEVICE_TYPE = 4   # MobileApplication -- we play the SAKE_SERVER role,
                            # matching this codebase's v1 SakeHandler already
                            # running pysake.server.SakeServer (also SERVER).


def _real_permit_material():
    """
    All three fields the permit exchange needs for our own key-database
    entry, sourced from the real, pump-extracted
    pysake.constants.KEYDB_PUMP_EXTRACTED -- see the module docstring above.
    """
    from pysake.constants import KEYDB_PUMP_EXTRACTED
    sk = KEYDB_PUMP_EXTRACTED.remote_devices[PUMP_DEVICE_TYPE]
    return sk.permit_decrypt_key, sk.permit_auth_key, sk.handshake_payload


@dataclass
class PermitKeys:
    """
    The material for our own key-database entry in the permit exchange
    (see the module docstring above). All three fields default to the
    real values already in KEYDB_PUMP_EXTRACTED -- no placeholders, no
    separate pump-side secret needed. Override only to point at a
    different account's key database, or to reproduce
    PythonSake's synthetic selftest_full_handshake.py values for testing.
    """
    decrypt_key: bytes = None
    mac_key: bytes = None
    outgoing_ciphertext: bytes = None

    def __post_init__(self):
        if self.decrypt_key is None or self.mac_key is None or self.outgoing_ciphertext is None:
            real_decrypt, real_mac, real_ciphertext = _real_permit_material()
            self.decrypt_key = self.decrypt_key or real_decrypt
            self.mac_key = self.mac_key or real_mac
            self.outgoing_ciphertext = self.outgoing_ciphertext or real_ciphertext
        for f in (self.decrypt_key, self.mac_key, self.outgoing_ciphertext):
            assert len(f) == 16


class SakeV2EngineAdapter:
    def __init__(self, passkey: int, permit_keys: PermitKeys = None):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        if permit_keys is None:
            self.logger.info(
                "SakeV2EngineAdapter: sourcing permit key material from the "
                "real KEYDB_PUMP_EXTRACTED (permit_decrypt_key/"
                "permit_auth_key/handshake_payload) -- see "
                "ble/sake_v2_engine.py's module docstring."
            )
            permit_keys = PermitKeys()

        engine = _sake_v2_engine_module()
        self._engine = engine

        our_material = engine.build_permit_key_material(
            permit_keys.decrypt_key,
            permit_keys.mac_key,
            permit_keys.outgoing_ciphertext,
        )
        keydb = engine.build_key_database(CONNECTOR_DEVICE_TYPE, PUMP_DEVICE_TYPE, our_material)
        self._server = engine.SakeV2Server(passkey, keydb)
        self._initial_message = None

    def initial_message(self) -> bytes:
        """
        The message to send to the pump to kick off the handshake -- v2's
        equivalent of v1's hardcoded bytes(20) "kick" in
        SakeHandler._handle_subscribe.
        """
        if self._initial_message is None:
            self._initial_message = self._server.step(None)
        return self._initial_message

    def handshake(self, input_data: bytes) -> bytes | None:
        try:
            return self._server.step(input_data)
        except self._engine.SakeHandshakeFailed as e:
            self.logger.error(f"protocol-v2 handshake failed: {e}")
            return None

    def is_done(self) -> bool:
        return self._server.is_done

    def encrypt(self, data: bytes) -> bytes:
        return self._server.secure_for_sending(data)

    def decrypt(self, data: bytes) -> bytes:
        return self._server.unsecure_after_receiving(data)
