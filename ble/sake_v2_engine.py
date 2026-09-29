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

What this does NOT yet have: real, per-pump identity-secret material for
the permit exchange (the four 16-byte AES/CMAC keys in PermitKeys below).
Those are provisioned per pump, most likely via the IDD Secure Control
Point (0x0109) / PublicKeyExchangeApiImpl flow this project's Documentation
repo describes -- not yet reverse engineered to the point of knowing how to
derive real values from it. Without real values here, this will complete a
handshake with anything running the same engine (see PythonSake's
selftest_full_handshake.py) but will NOT pair with a real pump.
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


@dataclass
class PermitKeys:
    """
    The four 16-byte identity secrets the permit exchange needs (see
    PythonSake's README for the exact protocol). All placeholder-default:
    NOT real pump key material -- a handshake built from these will only
    ever complete against another instance using the *same* values (e.g.
    PythonSake's own selftest), never a real pump.
    """
    our_decrypt_key: bytes = bytes(range(0xB0, 0xC0))
    our_mac_key: bytes = bytes(range(0xD0, 0xE0))
    peer_decrypt_key: bytes = bytes(range(0xA0, 0xB0))
    peer_mac_key: bytes = bytes(range(0xC0, 0xD0))

    def __post_init__(self):
        for f in (self.our_decrypt_key, self.our_mac_key, self.peer_decrypt_key, self.peer_mac_key):
            assert len(f) == 16


class SakeV2EngineAdapter:
    def __init__(self, passkey: int, permit_keys: PermitKeys = None):
        self.logger = LogManager.get_logger(self.__class__.__name__)
        if permit_keys is None:
            self.logger.warning(
                "SakeV2EngineAdapter: no real permit key material supplied -- "
                "using placeholder test values. This will NOT pair with a real "
                "pump. See ble/sake_v2_engine.py's module docstring."
            )
            permit_keys = PermitKeys()

        engine = _sake_v2_engine_module()
        self._engine = engine

        our_permit = engine.build_permit_plaintext(CONNECTOR_DEVICE_TYPE, permit_keys.peer_mac_key)
        our_material = engine.build_permit_key_material(
            permit_keys.our_decrypt_key,
            permit_keys.our_mac_key,
            engine.aes_ecb_encrypt(our_permit, permit_keys.peer_decrypt_key),
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
